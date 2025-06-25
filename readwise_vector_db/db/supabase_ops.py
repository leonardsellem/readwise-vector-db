import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, TypeVar

import asyncpg
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from readwise_vector_db.config import Settings, settings
from readwise_vector_db.db import get_pool

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SupabaseRetryConfig:
    """Configuration for Supabase-specific retry logic."""

    # Retry on connection issues, server errors, and timeout
    RETRYABLE_EXCEPTIONS = (
        asyncpg.ConnectionDoesNotExistError,
        asyncpg.ConnectionFailureError,
        asyncpg.PostgresConnectionError,
        asyncio.TimeoutError,
        OSError,  # Network-related issues
    )

    MAX_ATTEMPTS = 3
    MIN_WAIT = 1  # seconds
    MAX_WAIT = 8  # seconds
    MULTIPLIER = 2


async def with_supabase_retry(
    func, *args, max_attempts: int = SupabaseRetryConfig.MAX_ATTEMPTS, **kwargs
) -> Any:
    """
    Execute a database function with Supabase-compatible retry logic.

    This wrapper adds exponential backoff for transient connection errors
    that are common with serverless databases like Supabase.

    Args:
        func: The async function to execute
        *args: Arguments to pass to the function
        max_attempts: Maximum number of retry attempts
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Result of the function execution

    Raises:
        The last exception if all retries are exhausted
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=SupabaseRetryConfig.MULTIPLIER,
            min=SupabaseRetryConfig.MIN_WAIT,
            max=SupabaseRetryConfig.MAX_WAIT,
        ),
        retry=retry_if_exception_type(SupabaseRetryConfig.RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    ):
        with attempt:
            return await func(*args, **kwargs)


async def execute_vector_query(
    query: str,
    params: Optional[List[Any]] = None,
    fetch_all: bool = True,
    settings_obj: Optional[Settings] = None,
) -> Any:
    """
    Execute a vector-related SQL query using asyncpg with retry logic.

    This function uses the asyncpg pool for better connection management
    and includes Supabase-specific retry logic for transient failures.

    Args:
        query: SQL query string
        params: Query parameters
        fetch_all: If True, fetch all results; if False, fetch one
        settings_obj: Settings object (uses global if None)

    Returns:
        Query results
    """
    if settings_obj is None:
        settings_obj = settings

    pool = await get_pool(settings_obj)

    async def _execute():
        async with pool.acquire() as conn:
            if fetch_all:
                return await conn.fetch(query, *(params or []))
            else:
                return await conn.fetchrow(query, *(params or []))

    return await with_supabase_retry(_execute)


async def upsert_highlights_vectorized(
    highlights_data: List[Dict[str, Any]],
    batch_size: int = 100,
    settings_obj: Optional[Settings] = None,
) -> int:
    """
    Upsert highlights using vectorized operations with Supabase compatibility.

    This function performs batch upserts using native asyncpg for better
    performance and includes proper retry logic for Supabase.

    Args:
        highlights_data: List of highlight dictionaries to upsert
        batch_size: Number of records to process per batch
        settings_obj: Settings object (uses global if None)

    Returns:
        Total number of records processed
    """
    if not highlights_data:
        logger.info("No highlights to upsert.")
        return 0

    if settings_obj is None:
        settings_obj = settings

    pool = await get_pool(settings_obj)
    total_processed = 0

    # Process in batches to avoid overwhelming the connection
    for i in range(0, len(highlights_data), batch_size):
        current_batch = highlights_data[i : i + batch_size]

        async def _upsert_batch(batch_data: List[Dict[str, Any]]) -> int:
            async with pool.acquire() as conn:
                # Use PostgreSQL's ON CONFLICT for efficient upserts
                query = """
                    INSERT INTO highlight (
                        id, text, source_type, source_author, source_title,
                        source_url, category, note, location, highlighted_at,
                        tags, embedding
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (id) DO UPDATE SET
                        text = EXCLUDED.text,
                        source_type = EXCLUDED.source_type,
                        source_author = EXCLUDED.source_author,
                        source_title = EXCLUDED.source_title,
                        source_url = EXCLUDED.source_url,
                        category = EXCLUDED.category,
                        note = EXCLUDED.note,
                        location = EXCLUDED.location,
                        highlighted_at = EXCLUDED.highlighted_at,
                        tags = EXCLUDED.tags,
                        embedding = EXCLUDED.embedding
                """

                # Prepare batch data - ensure embedding is properly formatted
                batch_records = []
                for highlight in batch_data:
                    # Convert embedding list to PostgreSQL vector format if needed
                    embedding = highlight.get("embedding")
                    if embedding and isinstance(embedding, list):
                        # asyncpg handles list -> vector conversion automatically
                        pass

                    record = (
                        highlight.get("id"),
                        highlight.get("text"),
                        highlight.get("source_type"),
                        highlight.get("source_author"),
                        highlight.get("source_title"),
                        highlight.get("source_url"),
                        highlight.get("category"),
                        highlight.get("note"),
                        highlight.get("location"),
                        highlight.get("highlighted_at"),
                        highlight.get("tags"),
                        embedding,
                    )
                    batch_records.append(record)

                await conn.executemany(query, batch_records)
                return len(batch_records)

        batch_count = await with_supabase_retry(_upsert_batch, current_batch)
        total_processed += batch_count

        logger.info(
            f"Upserted batch of {batch_count} highlights (total: {total_processed})"
        )

        # Small delay between batches to be respectful to Supabase
        if settings_obj.is_serverless and i + batch_size < len(highlights_data):
            await asyncio.sleep(0.1)

    logger.info(f"Successfully upserted {total_processed} highlights total")
    return total_processed


async def vector_similarity_search(
    query_embedding: List[float],
    k: int = 5,
    source_type: Optional[str] = None,
    author: Optional[str] = None,
    tags: Optional[List[str]] = None,
    settings_obj: Optional[Settings] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Perform vector similarity search using native asyncpg for better performance.

    This function uses cosine distance with pgvector and includes proper
    Supabase compatibility and retry logic.

    Args:
        query_embedding: The query vector
        k: Number of results to return
        source_type: Filter by source type
        author: Filter by author
        tags: Filter by tags (any match)
        settings_obj: Settings object (uses global if None)

    Yields:
        Dictionary containing highlight data with similarity score
    """
    if settings_obj is None:
        settings_obj = settings

    # Build the WHERE clause dynamically
    where_conditions = ["embedding IS NOT NULL"]
    params: List[Any] = [query_embedding]
    param_idx = 2

    if source_type:
        where_conditions.append(f"source_type = ${param_idx}")
        params.append(source_type)
        param_idx += 1

    if author:
        where_conditions.append(f"source_author = ${param_idx}")
        params.append(author)
        param_idx += 1

    if tags:
        where_conditions.append(f"tags && ${param_idx}")
        params.append(tags)
        param_idx += 1

    where_clause = " AND ".join(where_conditions)

    # Use cosine distance with pgvector - compatible with Postgres 14+
    query = f"""
        SELECT
            id, text, source_type, source_author, source_title,
            source_url, category, note, location, highlighted_at,
            tags, embedding,
            embedding <=> $1 as score
        FROM highlight
        WHERE {where_clause}
        ORDER BY score
        LIMIT {k}
    """

    results = await execute_vector_query(
        query, params, fetch_all=True, settings_obj=settings_obj
    )

    for row in results:
        # Convert asyncpg Record to dict
        result = {
            "id": row["id"],
            "text": row["text"],
            "source_type": row["source_type"],
            "source_author": row["source_author"],
            "source_title": row["source_title"],
            "source_url": row["source_url"],
            "category": row["category"],
            "note": row["note"],
            "location": row["location"],
            "highlighted_at": row["highlighted_at"],
            "tags": row["tags"],
            "embedding": list(row["embedding"]) if row["embedding"] else None,
            "score": float(row["score"]),
        }
        yield result
