from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MemoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: dict[str, object]
    created_at: datetime
    updated_at: datetime
