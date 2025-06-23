import os
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import openai
from sqlmodel import and_, select

from readwise_vector_db.core.embedding import embed
from readwise_vector_db.db.database import get_session
from readwise_vector_db.models import Highlight


async def semantic_search(
    q: str,
    k: int,
    source_type: Optional[str] = None,
    author: Optional[str] = None,
    tags: Optional[List[str]] = None,
    highlighted_at_range: Optional[Tuple[date, date]] = None,
) -> List[Dict[str, Any]]:
    """
    Performs a semantic search for the given query with optional filters.
    """
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")

    oai_client = openai.AsyncClient(api_key=openai_api_key)
    q_emb = await embed(q, oai_client)

    async for session in get_session():
        stmt = select(
            Highlight, Highlight.embedding.cosine_distance(q_emb).label("score")  # type: ignore
        ).where(Highlight.__table__.c.embedding.isnot(None))

        filters = []
        if source_type is not None:
            filters.append(Highlight.source_type == source_type)
        if author is not None:
            filters.append(Highlight.author == author)
        if tags is not None:
            filters.append(Highlight.tags.op("&&")(tags))  # type: ignore
        if highlighted_at_range is not None:
            filters.append(Highlight.highlighted_at.between(*highlighted_at_range))  # type: ignore

        if filters:
            stmt = stmt.where(and_(*filters))

        stmt = stmt.limit(k).order_by("score")

        result = await session.exec(stmt)
        rows = result.all()

        return [{**row.Highlight.model_dump(), "score": row.score} for row in rows]

    return []
