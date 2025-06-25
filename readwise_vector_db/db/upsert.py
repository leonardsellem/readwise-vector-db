import logging
from datetime import datetime
from typing import List, Optional, cast

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from readwise_vector_db.config import Settings, settings
from readwise_vector_db.db.supabase_ops import (
    upsert_highlights_vectorized,
    with_supabase_retry,
)
from readwise_vector_db.models import Highlight, SyncState

logger = logging.getLogger(__name__)


async def get_sync_state(service: str, session: AsyncSession) -> Optional[SyncState]:
    """
    Retrieves the sync state for a given service.
    """
    result = await session.execute(
        select(SyncState).where(SyncState.service == service)
    )
    return cast(Optional[SyncState], result.scalar_one_or_none())


async def upsert_highlights(
    highlights: List[Highlight],
    session: AsyncSession,
    use_supabase_ops: bool = True,
    settings_obj: Optional[Settings] = None,
) -> None:
    """
    Inserts or updates a list of highlights in the database.

    Args:
        highlights: List of Highlight objects to upsert
        session: SQLModel async session
        use_supabase_ops: If True, use optimized Supabase operations with retry logic
        settings_obj: Settings object (uses global if None)
    """
    if not highlights:
        logger.info("No highlights to upsert.")
        return

    if settings_obj is None:
        settings_obj = settings

    # Auto-enable Supabase ops for Supabase backend or serverless deployments
    if use_supabase_ops and (
        settings_obj.DB_BACKEND == "supabase" or settings_obj.is_serverless
    ):
        # Convert Highlight objects to dictionaries for vectorized operation
        highlights_data = [h.model_dump() for h in highlights]

        # Use the new Supabase-compatible upsert with retry logic
        processed_count = await upsert_highlights_vectorized(
            highlights_data, batch_size=100, settings_obj=settings_obj
        )

        logger.info(
            f"Upserted {processed_count} highlights using Supabase-optimized operations."
        )
        return
    else:
        # Fall back to original SQLModel-based upsert
        await _upsert_highlights_sqlmodel(highlights, session)


async def _upsert_highlights_sqlmodel(
    highlights: List[Highlight], session: AsyncSession
) -> None:
    """
    Original SQLModel-based upsert for backward compatibility.

    This provides the same functionality as the original upsert_highlights
    but as a separate function for cleaner code organization.
    """
    values = [h.model_dump() for h in highlights]
    stmt = insert(Highlight).values(values)
    update_dict = {c.name: c for c in stmt.excluded if c.name not in ["id"]}

    on_conflict_stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_=update_dict,
    )
    await session.execute(on_conflict_stmt)
    await session.commit()
    logger.info(f"Upserted {len(highlights)} highlights using SQLModel operations.")


async def update_sync_state(
    service: str,
    session: AsyncSession,
    use_supabase_retry: bool = True,
    settings_obj: Optional[Settings] = None,
) -> None:
    """
    Updates the sync state for a given service to the current time.

    Args:
        service: Service name to update sync state for
        session: SQLModel async session
        use_supabase_retry: If True, wrap operations with Supabase retry logic
        settings_obj: Settings object (uses global if None)
    """
    if settings_obj is None:
        settings_obj = settings

    async def _update_sync_state() -> None:
        stmt = insert(SyncState).values(
            service=service, last_synced_at=datetime.utcnow()
        )
        update_dict = {
            "last_synced_at": stmt.excluded.last_synced_at,
        }
        on_conflict_stmt = stmt.on_conflict_do_update(
            index_elements=["service"],
            set_=update_dict,
        )
        await session.execute(on_conflict_stmt)
        await session.commit()
        logger.info(f"Updated sync state for service '{service}'.")

    # Apply retry logic for Supabase deployments
    if use_supabase_retry and (
        settings_obj.DB_BACKEND == "supabase" or settings_obj.is_serverless
    ):
        await with_supabase_retry(_update_sync_state)
    else:
        await _update_sync_state()
