from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SyncState(SQLModel, table=True):
    service: str = Field(primary_key=True)
    last_synced_at: Optional[datetime] = None
