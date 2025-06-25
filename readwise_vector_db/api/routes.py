"""API routes with lazy imports for optimized cold start performance.

This module contains all FastAPI routes with deferred imports to minimize
the initial loading time during serverless cold starts.
"""

import json
from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
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


async def _generate_sse_events(
    query: str,
    k: int = 20,
    source_type: Optional[str] = None,
    author: Optional[str] = None,
    tags: Optional[list[str]] = None,
    highlighted_at_range: Optional[list[str]] = None,
) -> str:
    """Generate SSE events for MCP streaming.
    
    Args:
        query: Search query text
        k: Number of results to return
        source_type: Filter by source type
        author: Filter by author  
        tags: Filter by tags
        highlighted_at_range: Date range filter as ISO strings
        
    Yields:
        SSE-formatted event strings
    """
    # Lazy imports to defer module loading
    import json
    
    from readwise_vector_db.mcp.search_service import SearchService

    try:
        # Use shared service to parse HTTP parameters
        search_params = SearchService.parse_http_params(
            query=query,
            k=k,
            source_type=source_type,
            author=author,
            tags=tags,
            from_date=highlighted_at_range[0] if highlighted_at_range and len(highlighted_at_range) > 0 else None,
            to_date=highlighted_at_range[1] if highlighted_at_range and len(highlighted_at_range) > 1 else None,
        )

        # Execute search using shared service
        result_count = 0
        async for result in SearchService.execute_search(search_params, stream=True, client_id="sse"):
            # Format as SSE event
            event_data = {
                "id": result["id"],
                "text": result["text"], 
                "score": result["score"],
                "source_type": result.get("source_type"),
                "author": result.get("author"),
                "title": result.get("title"),
                "url": result.get("url"),
                "tags": result.get("tags"),
                "highlighted_at": result.get("highlighted_at"),
                "updated_at": result.get("updated_at")
            }
            
            # Emit SSE event ↳ because SSE format requires "data: " prefix and double newlines
            yield f"event: result\ndata: {json.dumps(event_data)}\n\n"
            result_count += 1

        # Send completion event
        completion_data = {"type": "complete", "total_results": result_count}
        yield f"event: complete\ndata: {json.dumps(completion_data)}\n\n"

    except Exception as e:
        # Send error event
        error_data = {"type": "error", "message": str(e)}
        yield f"event: error\ndata: {json.dumps(error_data)}\n\n"


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

    @router.get("/mcp/stream")
    async def mcp_stream(
        request: Request,
        q: str = Query(..., description="Search query text"),
        k: int = Query(20, description="Number of results to return", ge=1, le=100),
        source_type: Optional[str] = Query(None, description="Filter by source type"),
        author: Optional[str] = Query(None, description="Filter by author"),
        tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
        highlighted_at_start: Optional[str] = Query(None, description="Start date for highlighted_at range (ISO format)"),
        highlighted_at_end: Optional[str] = Query(None, description="End date for highlighted_at range (ISO format)"),
    ) -> StreamingResponse:
        """MCP Server-Sent Events streaming endpoint.
        
        Streams semantic search results as SSE events for MCP clients.
        Compatible with serverless deployments like Vercel.
        
        Args:
            request: FastAPI request object for connection monitoring
            q: Search query text
            k: Number of results to return (1-100)
            source_type: Optional source type filter  
            author: Optional author filter
            tags: Optional comma-separated tags filter
            highlighted_at_start: Optional start date for date range filter
            highlighted_at_end: Optional end date for date range filter
            
        Returns:
            StreamingResponse with text/event-stream content type
        """
        # Parse tags from comma-separated string
        tags_list = None
        if tags:
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Build date range if both dates provided
        highlighted_at_range = None
        if highlighted_at_start and highlighted_at_end:
            highlighted_at_range = [highlighted_at_start, highlighted_at_end]

        async def event_generator():
            """Generator that monitors client connection and yields SSE events."""
            try:
                # Check if client is still connected before starting
                if await request.is_disconnected():
                    return

                async for event in _generate_sse_events(
                    q, k, source_type, author, tags_list, highlighted_at_range
                ):
                    # Check for client disconnect before each event
                    if await request.is_disconnected():
                        break
                    yield event

            except Exception as e:
                # Send error event if something goes wrong
                error_data = {"type": "error", "message": str(e)}
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",  # For CORS support
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )

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
