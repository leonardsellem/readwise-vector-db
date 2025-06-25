"""API routes with lazy imports for optimized cold start performance.

This module contains all FastAPI routes with deferred imports to minimize
the initial loading time during serverless cold starts.
"""

from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

# Global Prometheus metrics (initialized lazily)
rows_synced_total: Optional[Any] = None
error_rate: Optional[Any] = None
sync_duration_seconds: Optional[Any] = None


async def get_db():
    """Async generator for DB session (lazy imported dependency injection).

    This defers importing the database module until a request actually
    needs database access, improving cold start times.
    """
    # Lazy import to defer heavy database loading
    from readwise_vector_db.db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


def create_router() -> APIRouter:
    """Create API router with all endpoints.

    Returns:
        Configured APIRouter with all endpoints
    """
    router = APIRouter()

    @router.get("/health")
    async def health(db=Depends(get_db)) -> dict[str, str]:
        """Health check endpoint with database connectivity test.

        Returns:
            Status indicating service health
        """
        try:
            # Lazy import SQL execution to defer sqlalchemy loading
            from sqlalchemy import text

            # Run a simple query to check DB connectivity
            await db.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception:
            # If DB is unreachable, return 503
            raise HTTPException(
                status_code=HTTP_503_SERVICE_UNAVAILABLE, detail="DB unavailable"
            ) from None

    @router.post("/search")
    async def search(req: dict[str, Any]):
        """Semantic search endpoint with lazy imports.

        Args:
            req: Search request with query and parameters

        Returns:
            Search response with results
        """
        # Lazy imports to defer heavy module loading until needed
        from datetime import date

        from readwise_vector_db.core.search import semantic_search
        from readwise_vector_db.models.api import SearchRequest, SearchResponse

        # Parse request using lazy-loaded model
        search_req = SearchRequest(**req)

        highlighted_at = search_req.highlighted_at_range

        if (
            isinstance(highlighted_at, (list, tuple))
            and highlighted_at
            and isinstance(highlighted_at[0], str)
        ):
            # Convert incoming ISO date strings to date objects
            start_str, end_str = highlighted_at
            highlighted_at = (
                date.fromisoformat(start_str),
                date.fromisoformat(end_str),
            )

        results = cast(
            list[dict[str, str | None | int | float]],
            await semantic_search(
                search_req.q,
                search_req.k,
                search_req.source_type,
                search_req.author,
                search_req.tags,
                highlighted_at,
            ),
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

    return router


def _setup_prometheus_instrumentation(app: FastAPI) -> None:
    """Set up Prometheus instrumentation with lazy imports.

    Args:
        app: FastAPI application to instrument
    """
    # Lazy import prometheus components to defer loading
    from prometheus_client import Counter, Histogram
    from prometheus_fastapi_instrumentator import Instrumentator

    # Create custom metrics (these become module-level after first call)
    global rows_synced_total, error_rate, sync_duration_seconds

    if rows_synced_total is None:
        rows_synced_total = Counter(
            "rows_synced_total", "Total rows synced by the sync service"
        )
        error_rate = Counter("error_rate", "Total sync errors encountered")
        sync_duration_seconds = Histogram(
            "sync_duration_seconds", "Sync duration in seconds"
        )

    # Instrumentator setup (add Prometheus metrics to FastAPI app)
    Instrumentator().instrument(app).expose(app)


def setup_routes(app: FastAPI) -> None:
    """Set up all routes and instrumentation for the FastAPI app.

    Args:
        app: FastAPI application to configure
    """
    # Add API routes
    router = create_router()
    app.include_router(router)

    # Set up Prometheus instrumentation (lazy loaded)
    _setup_prometheus_instrumentation(app)
