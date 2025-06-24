from fastapi import APIRouter, Depends, FastAPI, HTTPException
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from datetime import date

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
    highlighted_at = req.highlighted_at_range

    if isinstance(highlighted_at, (list, tuple)) and highlighted_at and isinstance(
        highlighted_at[0], str
    ):
        # Convert incoming ISO date strings to date objects to match test expectations
        start_str, end_str = highlighted_at
        highlighted_at = (date.fromisoformat(start_str), date.fromisoformat(end_str))

    results = await semantic_search(
        req.q,
        req.k,
        req.source_type,
        req.author,
        req.tags,
        highlighted_at,
    )

    # Populate optional keys expected by tests when they are missing
    default_keys = {
        "source_id": None,
        "title": None,
        "author": None,
        "url": None,
        "tags": None,
        "highlighted_at": None,
        "updated_at": None,
    }
    for item in results:
        for k, v in default_keys.items():
            item.setdefault(k, v)

    return SearchResponse(results=results)


app.include_router(router)

# Instrumentator setup (add Prometheus metrics to FastAPI app)
Instrumentator().instrument(app).expose(app)

# Note: To increment custom metrics, call rows_synced_total.inc(), error_rate.inc(),
# and sync_duration_seconds.observe(duration) in the relevant sync code paths.
