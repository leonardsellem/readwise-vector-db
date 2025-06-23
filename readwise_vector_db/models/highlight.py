from typing import List, Optional

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from readwise_vector_db.models.helpers import SA_TYPE_TEXT_ARRAY


class Highlight(SQLModel, table=True):
    id: int = Field(primary_key=True)
    text: str
    source_type: str
    source_author: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    category: Optional[str] = None
    note: Optional[str] = None
    location: Optional[int] = None
    highlighted_at: Optional[str] = None
    tags: Optional[List[str]] = Field(
        default=None, sa_column=Column(SA_TYPE_TEXT_ARRAY)
    )
    embedding: Optional[List[float]] = Field(
        default=None, sa_column=Column(HALFVEC(3072))
    )
