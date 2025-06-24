from __future__ import annotations

import os
from datetime import date
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

import openai
from sqlmodel import and_, func, select

from readwise_vector_db.core.embedding import embed
from readwise_vector_db.db.database import get_session
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

    Yields:
        Dict containing highlight data with similarity score
    """
    # Compute query embedding
    client = get_openai_client()
    embedding = await embed(query, client)

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
) -> Union[List[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
    """
    Perform semantic search on highlights.

    Args:
        query: Search query text
        k: Number of results to return
        source_type: Filter by source type
        author: Filter by author
        tags: Filter by tags
        highlighted_at_range: Filter by highlighted date range (start_date, end_date)
        stream: If True, return results as an async iterator, otherwise collect and return as list

    Returns:
        If stream=True: AsyncIterator yielding search results as they're found
        If stream=False: List of search results
    """
    # Get the search generator with the provided parameters
    search_gen = _search_generator(
        query=query,
        k=k,
        source_type=source_type,
        author=author,
        tags=tags,
        highlighted_at_range=highlighted_at_range,
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
