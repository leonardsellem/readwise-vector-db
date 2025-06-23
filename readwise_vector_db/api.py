from fastapi import APIRouter, Depends, FastAPI, HTTPException
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from readwise_vector_db.core.search import semantic_search
from readwise_vector_db.db.database import AsyncSessionLocal
from readwise_vector_db.models.api import SearchRequest, SearchResponse

# Prometheus custom metrics (module-level singletons)
rows_synced_total = Counter(
    "rows_synced_total", "Total rows synced by the sync service"
)
error_rate = Counter("error_rate", "Total sync errors encountered")
sync_duration_seconds: Histogram = Histogram(
    "sync_duration_seconds", "Sync duration in seconds"
)


async def get_db() -> AsyncSession:
    """Async generator for DB session (for dependency injection)."""
    async with AsyncSessionLocal() as session:
        yield session


app = FastAPI(title="Readwise Vector DB")
router = APIRouter()


@router.get("/health")  # type: ignore
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    try:
        # Run a simple query to check DB connectivity
        await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        # If DB is unreachable, return 503
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE, detail="DB unavailable"
        ) from None


@router.post("/search", response_model=SearchResponse)  # type: ignore
async def search(req: SearchRequest) -> SearchResponse:
    results = await semantic_search(
        query=req.q,
        k=req.k,
        source_type=req.source_type,
        author=req.author,
        tags=req.tags,
        highlighted_at_range=req.highlighted_at_range,
        stream=False,  # Use non-streaming mode for FastAPI
    )
    return SearchResponse(results=results)


app.include_router(router)

# Instrumentator setup (add Prometheus metrics to FastAPI app)
Instrumentator().instrument(app).expose(app)

# Note: To increment custom metrics, call rows_synced_total.inc(), error_rate.inc(),
# and sync_duration_seconds.observe(duration) in the relevant sync code paths.
