from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReceiptItemRead(BaseModel):
    name: str
    quantity: Decimal | None = None
    amount: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)


class ReceiptCandidateRead(BaseModel):
    merchant: str | None
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    occurred_at: datetime
    category_id: UUID | None
    category_name: str | None
    description: str
    receipt_image_url: str
    raw_ocr_data: dict[str, Any]
    items: list[ReceiptItemRead]
    confidence: Decimal = Field(ge=0, le=1)
