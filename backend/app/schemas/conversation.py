from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConversationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    started_at: datetime
    last_message_at: datetime | None
    message_count: int
    preview: str | None


class ConversationMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_name: str | None
    created_at: datetime


class ConversationMessages(BaseModel):
    conversation_id: UUID
    started_at: datetime
    message_count: int
    messages: list[ConversationMessage]
