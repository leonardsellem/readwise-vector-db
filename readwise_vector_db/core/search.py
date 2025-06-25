from __future__ import annotations

import os
from datetime import date
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

import openai
from sqlmodel import and_, func, select

from readwise_vector_db.config import Settings, settings
from readwise_vector_db.core.embedding import embed
from readwise_vector_db.db.database import get_session
from readwise_vector_db.db.supabase_ops import vector_similarity_search
from readwise_vector_db.models import Highlight

# mypy: ignore-errors


# Cache the OpenAI client to avoid recreation
_openai_client: Optional[openai.AsyncClient] = None


def get_openai_client() -> openai.AsyncClient:
    """
    Gets or creates an OpenAI client singleton.

    Returns:
        AsyncClient: OpenAI async client

    Raises:
        ValueError: If OPENAI_API_KEY environment variable is not set
    """
    global _openai_client

    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable must be set")
        _openai_client = openai.AsyncClient(api_key=api_key)

    return _openai_client


async def _search_generator(
    query: str,
    k: int = 5,
    source_type: Optional[str] = None,
    author: Optional[str] = None,
    tags: Optional[List[str]] = None,
    highlighted_at_range: Optional[Tuple[date, date]] = None,
    use_supabase_ops: bool = True,
    settings_obj: Optional[Settings] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Internal generator function that performs the actual semantic search.

    Args:
        query: Search query text
        k: Number of results to return
        source_type: Filter by source type
        author: Filter by author
        tags: Filter by tags
        highlighted_at_range: Filter by highlighted date range (start_date, end_date)
        use_supabase_ops: If True, use optimized Supabase operations with retry logic
        settings_obj: Settings object (uses global if None)

    Yields:
        Dict containing highlight data with similarity score
    """
    if settings_obj is None:
        settings_obj = settings

    # Compute query embedding
    client = get_openai_client()
    embedding = await embed(query, client)

    # Use optimized Supabase operations if enabled and supported
    if use_supabase_ops and (
        settings_obj.DB_BACKEND == "supabase" or settings_obj.is_serverless
    ):
        # Use the new Supabase-compatible search with retry logic
        async for result in vector_similarity_search(
            query_embedding=embedding,
            k=k,
            source_type=source_type,
            author=author,
            tags=tags,
            settings_obj=settings_obj,
        ):
            # Note: highlighted_at_range filtering not yet implemented in supabase_ops
            # TODO: Add date range filtering to vector_similarity_search
            if highlighted_at_range is not None:
                # For now, fall back to post-filtering
                highlighted_at = result.get("highlighted_at")
                if highlighted_at:
                    # Convert string to date for comparison if needed
                    if isinstance(highlighted_at, str):
                        try:
                            from datetime import datetime

                            highlighted_date = datetime.fromisoformat(
                                highlighted_at.replace("Z", "+00:00")
                            ).date()
                            start_date, end_date = highlighted_at_range
                            if not (start_date <= highlighted_date <= end_date):
                                continue
                        except (ValueError, TypeError):
                            # Skip if we can't parse the date
                            continue
                    elif hasattr(highlighted_at, "date"):
                        start_date, end_date = highlighted_at_range
                        if not (start_date <= highlighted_at.date() <= end_date):
                            continue

            yield result
    else:
        # Fall back to original SQLModel-based search for compatibility
        async for result in _search_generator_sqlmodel(
            query, k, source_type, author, tags, highlighted_at_range, embedding
        ):
            yield result


async def _search_generator_sqlmodel(
    query: str,
    k: int,
    source_type: Optional[str],
    author: Optional[str],
    tags: Optional[List[str]],
    highlighted_at_range: Optional[Tuple[date, date]],
    embedding: List[float],
) -> AsyncIterator[Dict[str, Any]]:
    """
    Original SQLModel-based search generator for backward compatibility.

    This provides the same functionality as the original _search_generator
    but as a separate function for cleaner code organization.
    """
    # Build the query
    stmt = select(
        Highlight, func.cosine_distance(Highlight.embedding, embedding).label("score")
    ).where(Highlight.__table__.c.embedding.isnot(None))

    # Apply filters
    filters = []

    if source_type:
        filters.append(Highlight.source_type == source_type)

    if author:
        filters.append(Highlight.author == author)

    # Safely handle tags with proper None check
    if tags is not None and len(tags) > 0:
        filters.append(Highlight.tags.op("&&")(tags))  # type: ignore[union-attr]

    # Safely handle highlighted_at_range with proper None check
    if highlighted_at_range is not None:
        start_date, end_date = highlighted_at_range
        filters.append(Highlight.highlighted_at.between(start_date, end_date))  # type: ignore[union-attr]

    if filters:
        stmt = stmt.where(and_(*filters))

    # Order by similarity and limit results
    stmt = stmt.order_by("score").limit(k)

    # Execute query
    async for session in get_session():
        # Support both plain session objects (with exec) and context managers
        if hasattr(session, "__aenter__"):
            async with session as s:
                results_iter = await s.exec(stmt)
        elif hasattr(session, "exec"):
            results_iter = await session.exec(stmt)
        else:  # pragma: no cover – unexpected stub type
            continue

        for row in results_iter:
            highlight_dict = row.Highlight.model_dump()

            # Add the similarity score
            highlight_dict["score"] = float(row.score)

            yield highlight_dict


async def semantic_search(
    query: str,
    k: int = 5,
    source_type: Optional[str] = None,
    author: Optional[str] = None,
    tags: Optional[List[str]] = None,
    highlighted_at_range: Optional[Tuple[date, date]] = None,
    stream: bool = False,
    use_supabase_ops: bool = True,
    settings_obj: Optional[Settings] = None,
) -> Union[List[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
    """
    Perform semantic search on highlights with Supabase compatibility.

    Args:
        query: Search query text
        k: Number of results to return
        source_type: Filter by source type
        author: Filter by author
        tags: Filter by tags
        highlighted_at_range: Filter by highlighted date range (start_date, end_date)
        stream: If True, return results as an async iterator, otherwise collect and return as list
        use_supabase_ops: If True, use optimized Supabase operations (auto-detected by default)
        settings_obj: Settings object (uses global if None)

    Returns:
        If stream=True: AsyncIterator yielding search results as they're found
        If stream=False: List of search results
    """
    if settings_obj is None:
        settings_obj = settings

    # Auto-enable Supabase ops for Supabase backend or serverless deployments
    if (
        use_supabase_ops is True
        and settings_obj.DB_BACKEND != "supabase"
        and not settings_obj.is_serverless
    ):
        use_supabase_ops = False

    # Get the search generator with the provided parameters
    search_gen = _search_generator(
        query=query,
        k=k,
        source_type=source_type,
        author=author,
        tags=tags,
        highlighted_at_range=highlighted_at_range,
        use_supabase_ops=use_supabase_ops,
        settings_obj=settings_obj,
    )

    if stream:
        # Return the generator directly for streaming
        return search_gen
    else:
        # Collect all results from the iterator
        results = []
        async for result in search_gen:
            results.append(result)
        return results
