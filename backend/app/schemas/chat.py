from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatStreamRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    conversation_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Mesaj boş olamaz.")
        return normalized
