from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    started_at: datetime
    last_message_at: datetime | None
    message_count: int
    preview: str | None


class ConversationAttachment(BaseModel):
    type: Literal["chart", "image", "report"]
    chart: dict[str, Any] | None = None
    image_url: str | None = None
    alt_text: str | None = None
    report_id: str | None = None
    download_url: str | None = None
    filename: str | None = None
    title: str | None = None
    format: str | None = None


class ConversationMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_name: str | None
    created_at: datetime
    attachments: list[ConversationAttachment] = Field(default_factory=list)


class ConversationMessages(BaseModel):
    conversation_id: UUID
    started_at: datetime
    message_count: int
    messages: list[ConversationMessage]
