"""Database abstraction layer supporting multiple backends and deployment targets."""

import warnings
from typing import Any, Optional

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from readwise_vector_db.config import DatabaseBackend, Settings


def database_url(settings: Settings) -> str:
    """Generate database URL based on backend configuration.

    Args:
        settings: Application settings containing database configuration

    Returns:
        Database URL string for the selected backend

    Raises:
        ValueError: If required configuration is missing
    """
    if settings.db_backend == DatabaseBackend.SUPABASE:
        if not settings.supabase_db_url:
            raise ValueError(
                "SUPABASE_DB_URL is required when DB_BACKEND is 'supabase'"
            )
        return _ensure_asyncpg_driver(settings.supabase_db_url)

    # Local backend
    if settings.local_db_url:
        return _ensure_asyncpg_driver(settings.local_db_url)

    # Fallback to environment variables for backward compatibility
    import os

    database_url_env = os.environ.get("DATABASE_URL")
    if database_url_env:
        return _ensure_asyncpg_driver(database_url_env)

    # Final fallback: construct from individual variables
    pg_user = os.environ.get("POSTGRES_USER", "postgres")
    pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    pg_db = os.environ.get("POSTGRES_DB", "readwise")
    return f"postgresql+asyncpg://{pg_user}:{pg_password}@localhost:5432/{pg_db}"


def _ensure_asyncpg_driver(url: str) -> str:
    """Ensure the database URL uses the asyncpg driver.

    Args:
        url: Database URL that may use sync drivers

    Returns:
        Database URL with asyncpg driver
    """
    if "+asyncpg" in url or "+psycopg_async" in url:
        return url  # Already async-compatible

    _needs_patch = False
    if "+psycopg" in url or "+psycopg2" in url:
        _needs_patch = True
    elif url.startswith("postgresql://") and "+" not in url.split("postgresql", 1)[1]:
        _needs_patch = True  # Plain driverless URL

    if _needs_patch:
        warnings.warn(
            "Database URL uses a synchronous Postgres driver. Switching to '+asyncpg' "
            "for async SQLAlchemy compatibility. Update your configuration to avoid "
            "this warning.",
            stacklevel=3,
        )

        if "+" in url:
            # Replace the driver part
            head, rest = url.split("+", 1)
            rest = rest.split("://", 1)[1]
            return f"{head}+asyncpg://{rest}"
        else:
            # Insert asyncpg driver
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return url


def _asyncpg_url_from_sqlalchemy(sqlalchemy_url: str) -> str:
    """Convert SQLAlchemy URL to plain asyncpg URL.

    Args:
        sqlalchemy_url: SQLAlchemy URL that may contain driver specifications

    Returns:
        Plain PostgreSQL URL compatible with asyncpg.create_pool()

    Examples:
        postgresql+asyncpg://user:pass@host:port/db -> postgresql://user:pass@host:port/db
        postgresql+psycopg://user:pass@host:port/db -> postgresql://user:pass@host:port/db
        postgresql://user:pass@host:port/db -> postgresql://user:pass@host:port/db
    """
    if "+" not in sqlalchemy_url:
        return sqlalchemy_url  # Already plain URL

    # Split on the first + to separate scheme from driver
    scheme_part, rest = sqlalchemy_url.split("+", 1)

    # Extract everything after the driver specification
    if "://" in rest:
        _, connection_part = rest.split("://", 1)
        return f"{scheme_part}://{connection_part}"

    return sqlalchemy_url  # Fallback to original if format is unexpected


def get_engine_config(settings: Settings) -> dict[str, Any]:
    """Get SQLAlchemy engine configuration based on deployment target.

    Args:
        settings: Application settings

    Returns:
        Dictionary of engine configuration parameters
    """
    config = {
        "echo": False,
        "future": True,
    }

    # Optimize for serverless environments
    if settings.is_serverless:
        config.update(
            {
                "pool_size": 1,  # type: ignore[dict-item]
                "max_overflow": 4,  # type: ignore[dict-item]
                "pool_pre_ping": True,  # Verify connections before use
                "pool_recycle": 3600,  # type: ignore[dict-item]  # Recycle connections after 1 hour
            }
        )
    else:
        # Standard configuration for long-running containers
        config.update(
            {
                "pool_size": 5,  # type: ignore[dict-item]
                "max_overflow": 10,  # type: ignore[dict-item]
                "pool_pre_ping": True,
            }
        )

    return config


# Global connection pool and engine (lazily initialized)
_engine: Optional[AsyncEngine] = None
_session_maker: Optional[sessionmaker] = None
_pool: Optional[asyncpg.Pool] = None


def get_engine(settings: Optional[Settings] = None) -> AsyncEngine:
    """Get or create the SQLAlchemy async engine.

    Args:
        settings: Application settings (uses global if not provided)

    Returns:
        Configured async engine instance
    """
    global _engine

    if _engine is None:
        if settings is None:
            from readwise_vector_db.config import settings as global_settings

            settings = global_settings

        url = database_url(settings)
        config = get_engine_config(settings)
        _engine = create_async_engine(url, **config)

    return _engine


def get_session_maker(settings: Optional[Settings] = None) -> sessionmaker:
    """Get or create the session maker.

    Args:
        settings: Application settings

    Returns:
        Configured session maker
    """
    global _session_maker

    if _session_maker is None:
        engine = get_engine(settings)
        _session_maker = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

    return _session_maker


async def get_pool(settings: Optional[Settings] = None) -> asyncpg.Pool:
    """Get or create the asyncpg connection pool for direct database access.

    This is useful for operations that need direct asyncpg access,
    like bulk operations or custom SQL that bypasses SQLAlchemy.

    Args:
        settings: Application settings

    Returns:
        asyncpg connection pool
    """
    global _pool

    if _pool is None:
        if settings is None:
            from readwise_vector_db.config import settings as global_settings

            settings = global_settings

        url = database_url(settings)

        # Configure pool size based on deployment target
        if settings.is_serverless:
            min_size, max_size = 0, 5  # Conservative for serverless
        else:
            min_size, max_size = 2, 10  # Standard for containers

        # Convert SQLAlchemy URL to plain asyncpg URL format
        asyncpg_url = _asyncpg_url_from_sqlalchemy(url)

        _pool = await asyncpg.create_pool(
            asyncpg_url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=30,
        )

    return _pool


async def get_session() -> AsyncSession:
    """Get a database session.

    This is the main dependency for FastAPI endpoints.

    Yields:
        AsyncSession: Database session
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


async def close_connections() -> None:
    """Close all database connections and pools.

    This should be called during application shutdown.
    """
    global _engine, _pool, _session_maker

    if _engine:
        await _engine.dispose()
        _engine = None

    if _pool:
        await _pool.close()
        _pool = None

    _session_maker = None
