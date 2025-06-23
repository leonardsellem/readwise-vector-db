from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SyncState(SQLModel, table=True):  # type: ignore
    id: int = Field(default=1, primary_key=True)
    last_sync: datetime
    service: str = Field(primary_key=True)
    last_synced_at: Optional[datetime] = None
