import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from readwise_vector_db.models import Highlight, SyncState

logger = logging.getLogger(__name__)


async def get_sync_state(service: str, session: AsyncSession) -> Optional[SyncState]:
    """
    Retrieves the sync state for a given service.
    """
    result = await session.execute(
        select(SyncState).where(SyncState.service == service)
    )
    return result.scalar_one_or_none()


async def upsert_highlights(highlights: List[Highlight], session: AsyncSession) -> None:
    """
    Inserts or updates a list of highlights in the database.
    """
    if not highlights:
        logger.info("No highlights to upsert.")
        return

    values = [h.model_dump() for h in highlights]
    stmt = insert(Highlight).values(values)
    update_dict = {c.name: c for c in stmt.excluded if c.name not in ["id"]}

    on_conflict_stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_=update_dict,
    )
    await session.execute(on_conflict_stmt)
    await session.commit()
    logger.info(f"Upserted {len(highlights)} highlights.")


async def update_sync_state(service: str, session: AsyncSession) -> None:
    """
    Updates the sync state for a given service to the current time.
    """
    stmt = insert(SyncState).values(service=service, last_synced_at=datetime.utcnow())
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
