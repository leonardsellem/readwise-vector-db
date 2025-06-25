"""Database connection and session management with unified config system.

This module provides database connectivity using the new unified config system
from readwise_vector_db.config, supporting both local and Supabase backends.
"""

import warnings
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from readwise_vector_db.config import DatabaseBackend, settings

# Global instances (initialized lazily)
engine: AsyncEngine = None
AsyncSessionLocal: Any = None


def _get_database_url() -> str:
    """Get the appropriate database URL based on configuration.
    
    Returns:
        Database URL with async driver
        
    Raises:
        ValueError: If no valid database configuration is found
    """
    database_url = None
    
    # Determine database URL based on backend configuration
    if settings.db_backend == DatabaseBackend.SUPABASE:
        database_url = settings.supabase_db_url
        if not database_url:
            raise ValueError(
                "SUPABASE_DB_URL is required when DB_BACKEND is 'supabase'. "
                "Please set the environment variable."
            )
    else:
        # Local backend
        database_url = settings.local_db_url
        if not database_url:
            # Construct default local URL
            # ↳ Use environment variables as fallback for local development
            import os
            pg_user = os.environ.get("POSTGRES_USER", "postgres")
            pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
            pg_db = os.environ.get("POSTGRES_DB", "readwise")
            database_url = (
                f"postgresql+asyncpg://{pg_user}:{pg_password}@localhost:5432/{pg_db}"
            )
    
    # Ensure async-compatible driver
    # ↳ Convert sync drivers to asyncpg for proper async support
    if database_url and not any(driver in database_url for driver in ["+asyncpg", "+psycopg_async"]):
        if any(driver in database_url for driver in ["+psycopg", "+psycopg2"]) or database_url.startswith("postgresql://"):
            warnings.warn(
                "Database URL uses a synchronous Postgres driver. Switching to '+asyncpg' "
                "so the async SQLAlchemy engine works correctly. Update your configuration "
                "to avoid this warning.",
                stacklevel=2,
            )
            
            # Normalize to the `postgresql+asyncpg://` scheme
            if "+" in database_url:
                head, rest = database_url.split("+", 1)
                rest = rest.split("://", 1)[1]
                database_url = f"{head}+asyncpg://{rest}"
            else:
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    return database_url


def _initialize_database():
    """Initialize the database engine and session factory.
    
    This is called lazily when first needed to improve cold start times.
    """
    global engine, AsyncSessionLocal
    
    if engine is None:
        database_url = _get_database_url()
        
        # Create async engine with appropriate settings
        engine = create_async_engine(
            database_url, 
            echo=False, 
            future=True,
            # ↳ Connection pool settings for serverless environments
            pool_size=1 if settings.is_serverless else 5,
            max_overflow=0 if settings.is_serverless else 10,
            pool_pre_ping=True,  # Validate connections before use
        )

        AsyncSessionLocal = sessionmaker(
            engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session.
    
    Yields:
        AsyncSession: Database session for async operations
    """
    if AsyncSessionLocal is None:
        _initialize_database()
    
    async with AsyncSessionLocal() as session:
        yield session


async def get_pool():
    """Initialize database pool for pre-warming.
    
    This is called during application startup to establish
    initial database connections and reduce first-request latency.
    """
    if engine is None:
        _initialize_database()
    
    # Test the connection to ensure it's working
    # ↳ Import here to avoid circular imports and defer loading
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def close_connections():
    """Close all database connections.
    
    This is called during application shutdown to clean up resources.
    """
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None
