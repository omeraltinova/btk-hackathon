from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ApprovalDecision = str


class ChatStreamRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    conversation_id: UUID | None = None
    receipt_image_base64: str | None = Field(default=None, max_length=7_000_000)
    receipt_filename: str | None = Field(default=None, max_length=120)
    receipt_content_type: str | None = Field(default=None, max_length=80)
    approval_id: str | None = Field(default=None, max_length=80)
    approval_decision: ApprovalDecision | None = Field(default=None, max_length=16)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Mesaj boş olamaz.")
        return normalized

    @field_validator("receipt_filename", "receipt_content_type")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("approval_decision")
    @classmethod
    def normalize_approval_decision(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).casefold()
        if normalized not in {"approved", "rejected"}:
            raise ValueError("Onay kararı approved veya rejected olmalı.")
        return normalized
