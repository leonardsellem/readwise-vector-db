"""Optimized FastAPI application with serverless cold start optimizations.

This module provides a get_application() function that returns a FastAPI app
wrapped with LifespanManager for proper ASGI lifespan event handling.
Heavy imports are deferred until actually needed to minimize cold start times.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from asgi_lifespan import LifespanManager
from fastapi import FastAPI

# Global state for database initialization
_db_initialized = False


async def init_pool() -> None:
    """Initialize database pool during application startup.

    This function is called during ASGI lifespan startup to pre-warm
    the database connection pool, reducing latency for first requests.
    """
    global _db_initialized

    if not _db_initialized:
        # Lazy import to defer loading heavy modules
        from readwise_vector_db.db import get_pool

        # Initialize the asyncpg pool (this will create it if not exists)
        await get_pool()
        _db_initialized = True


async def close_pool() -> None:
    """Close database connections during application shutdown.

    This ensures graceful cleanup of resources when the application
    terminates, preventing connection leaks.
    """
    global _db_initialized

    if _db_initialized:
        # Lazy import to defer loading heavy modules
        from readwise_vector_db.db import close_connections

        await close_connections()
        _db_initialized = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """ASGI lifespan context manager for startup/shutdown events.

    This replaces the deprecated @app.on_event("startup") and
    @app.on_event("shutdown") decorators with the modern lifespan approach.
    """
    # Startup: Initialize database pool
    await init_pool()

    try:
        yield
    finally:
        # Shutdown: Clean up database connections
        await close_pool()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application with all routes and middleware
    """
    # Determine if we're in production (disable docs for performance)
    is_production = os.getenv("VERCEL_ENV") == "production"

    app = FastAPI(
        title="Readwise Vector DB",
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
    )

    # Lazy import routes to defer loading heavy dependencies
    from .routes import setup_routes

    setup_routes(app)

    return app


def get_application() -> LifespanManager:
    """Get the ASGI application wrapped with LifespanManager.

    This is the main entry point for ASGI servers. The LifespanManager
    ensures compatibility with ASGI servers that may not fully support
    the lifespan protocol.

    Returns:
        LifespanManager wrapping the FastAPI application
    """
    app = create_app()
    return LifespanManager(app)


# For backward compatibility and direct uvicorn usage
app = create_app()
