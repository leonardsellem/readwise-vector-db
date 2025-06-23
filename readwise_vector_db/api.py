from fastapi import APIRouter, FastAPI

from readwise_vector_db.core.search import semantic_search
from readwise_vector_db.models.api import SearchRequest, SearchResponse

app = FastAPI(title="Readwise Vector DB")
router = APIRouter()


@router.get("/health")  # type: ignore
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/search", response_model=SearchResponse)  # type: ignore
async def search(req: SearchRequest) -> SearchResponse:
    results = await semantic_search(
        req.q,
        req.k,
        req.source_type,
        req.author,
        req.tags,
        req.highlighted_at_range,
    )
    return SearchResponse(results=results)


app.include_router(router)
