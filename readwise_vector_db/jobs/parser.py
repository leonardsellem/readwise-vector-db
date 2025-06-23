from datetime import datetime
from typing import Any, Dict, Optional

from readwise_vector_db.models import Highlight


def parse_iso_datetime(date_string: Optional[str]) -> Optional[datetime]:
    if not date_string:
        return None
    try:
        # Handles a format like "2022-09-13T16:41:53.186Z"
        if date_string.endswith("Z"):
            date_string = date_string[:-1] + "+00:00"
        return datetime.fromisoformat(date_string)
    except (ValueError, TypeError):
        return None


def parse_highlight(raw_highlight: Dict[str, Any]) -> Highlight:
    """Parses a raw highlight dictionary from the Readwise API into a Highlight model."""
    book_info = raw_highlight.get("book", {})
    tags_list = raw_highlight.get("tags", [])

    return Highlight(
        id=raw_highlight["id"],
        text=raw_highlight["text"],
        source_type=book_info.get("category"),
        source_id=str(book_info.get("id")) if book_info.get("id") is not None else None,
        title=book_info.get("title"),
        author=book_info.get("author"),
        url=raw_highlight.get("url") or book_info.get("source_url"),
        tags=[tag["name"] for tag in tags_list if "name" in tag],
        highlighted_at=parse_iso_datetime(raw_highlight.get("highlighted_at")),
        updated_at=parse_iso_datetime(raw_highlight.get("updated_at")),
        embedding=[],  # Placeholder, will be added before upserting
    )
