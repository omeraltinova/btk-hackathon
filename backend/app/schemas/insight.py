from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

InsightSeverity = Literal["info", "warning", "critical"]


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    insight_type: str
    title: str
    content: str
    severity: InsightSeverity
    action_label: str | None
    is_dismissed: bool
    created_at: datetime
    updated_at: datetime
