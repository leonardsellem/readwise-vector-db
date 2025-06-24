import os

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Construct default URL that *explicitly* uses the async-friendly driver
    pg_user = os.environ.get("POSTGRES_USER", "postgres")
    pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    pg_db = os.environ.get("POSTGRES_DB", "readwise")
    DATABASE_URL = (
        f"postgresql+asyncpg://{pg_user}:{pg_password}@localhost:5432/{pg_db}"
    )

# ── Safety net ────────────────────────────────────────────────────────────────
# If the user supplied a DATABASE_URL that mistakenly points at a *sync* driver
# (e.g. the common `+psycopg` example), automatically switch it to `+asyncpg`
# so the async engine initialisation does not explode with
# `sqlalchemy.exc.InvalidRequestError: The asyncio extension requires an async driver`.
#
# We do this transformation only when **all** of these are true:
#   1. `DATABASE_URL` is present from the environment, and
#   2. It contains `+psycopg` (sync driver alias), and
#   3. It *does not* already specify `psycopg_async` (the async alias), and
#   4. It *does not* already specify `+asyncpg` (the proper async driver).
#
# This keeps the behaviour safe for users who intentionally chose another
# async-ready dialect (e.g. `psycopg_async`).

if (
    DATABASE_URL
    and "+psycopg" in DATABASE_URL
    and "+psycopg_async" not in DATABASE_URL
    and "+asyncpg" not in DATABASE_URL
):
    # Emit a gentle warning so the user is aware of the change.
    import warnings

    warnings.warn(
        "DATABASE_URL used '+psycopg' (sync driver). Switching to '+asyncpg' "
        "for async compatibility. Consider updating your .env accordingly.",
        stacklevel=2,
    )
    DATABASE_URL = DATABASE_URL.replace("+psycopg", "+asyncpg")

# The engine should be asynchronous - this fixes the AsyncEngine expected error
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
