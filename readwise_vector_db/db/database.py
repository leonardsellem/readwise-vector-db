import os

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Construct from components if DATABASE_URL is not set
    pg_user = os.environ.get("POSTGRES_USER", "postgres")
    pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    pg_db = os.environ.get("POSTGRES_DB", "readwise")
    # Use asyncpg for proper async support with AsyncSession
    DATABASE_URL = (
        f"postgresql+asyncpg://{pg_user}:{pg_password}@localhost:5432/{pg_db}"
    )

# The engine should be asynchronous - this fixes the AsyncEngine expected error
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
