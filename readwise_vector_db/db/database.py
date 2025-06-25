import os

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

# ↳ Import the new configuration system
from readwise_vector_db.config import settings


# Use the new configuration system to get the correct database URL
def get_database_url() -> str:
    """Get the appropriate database URL based on the current configuration."""
    if settings.db_backend.value == "supabase":
        if not settings.supabase_db_url:
            raise ValueError(
                "SUPABASE_DB_URL is required when DB_BACKEND is 'supabase'"
            )
        return settings.supabase_db_url
    else:
        # Local database
        if settings.local_db_url:
            return settings.local_db_url

        # Fallback to legacy DATABASE_URL or construct default
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            return database_url

        # Construct default local URL
        pg_user = os.environ.get("POSTGRES_USER", "postgres")
        pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
        pg_db = os.environ.get("POSTGRES_DB", "readwise")
        return f"postgresql+asyncpg://{pg_user}:{pg_password}@localhost:5432/{pg_db}"


DATABASE_URL = get_database_url()

# Convert to asyncpg unless the URL already specifies an async-friendly driver
# We catch three situations:
#   • `+psycopg` (sync alias)
#   • `+psycopg2` (common alias when using psycopg2-binary)
#   • *no explicit driver* (plain `postgresql://`)

if DATABASE_URL:
    _needs_patch = False

    if "+asyncpg" in DATABASE_URL or "+psycopg_async" in DATABASE_URL:
        _needs_patch = False  # Already async-compatible
    elif "+psycopg" in DATABASE_URL or "+psycopg2" in DATABASE_URL:
        _needs_patch = True
    elif (
        DATABASE_URL.startswith("postgresql://")
        and "+" not in DATABASE_URL.split("postgresql", 1)[1]
    ):
        # Plain driverless URL, SQLAlchemy will pick psycopg2 by default
        _needs_patch = True

    if _needs_patch:
        import warnings

        warnings.warn(
            "DATABASE_URL uses a synchronous Postgres driver. Switching to '+asyncpg' "
            "so the async SQLAlchemy engine works correctly. Update your .env to avoid "
            "this warning.",
            stacklevel=2,
        )

        # Normalise to the `postgresql+asyncpg://` scheme
        if "+" in DATABASE_URL:
            # Replace the bit after '+' up to '://'
            head, rest = DATABASE_URL.split("+", 1)
            rest = rest.split("://", 1)[1]
            DATABASE_URL = f"{head}+asyncpg://{rest}"
        else:
            # Simply insert '+asyncpg'
            DATABASE_URL = DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

# The engine should be asynchronous - this fixes the AsyncEngine expected error
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
