from typing import List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    q: str = Field(..., description="The search query.")
    k: int = Field(20, description="The number of results to return.")


class SearchResult(BaseModel):
    id: str
    text: str
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    tags: Optional[List[str]] = None
    highlighted_at: Optional[str] = None
    updated_at: Optional[str] = None
    embedding: Optional[List[float]] = None
    score: float


class SearchResponse(BaseModel):
    results: List[SearchResult]
