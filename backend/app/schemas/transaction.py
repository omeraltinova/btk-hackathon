from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

TransactionType = Literal["income", "expense"]
TransactionSource = Literal["manual", "receipt_ocr", "recurring"]


class TransactionCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    type: TransactionType
    category_id: UUID | None = None
    description: str | None = Field(default=None, max_length=240)
    merchant: str | None = Field(default=None, max_length=120)
    occurred_at: datetime
    source: TransactionSource = "manual"
    receipt_image_url: str | None = Field(default=None, max_length=500)
    raw_ocr_data: dict[str, Any] | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Tarih saat dilimi içermeli.")
        return value

    @field_validator("description", "merchant")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class TransactionUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    type: TransactionType | None = None
    category_id: UUID | None = None
    description: str | None = Field(default=None, max_length=240)
    merchant: str | None = Field(default=None, max_length=120)
    occurred_at: datetime | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Tarih saat dilimi içermeli.")
        return value

    @field_validator("description", "merchant")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    amount: Decimal
    type: TransactionType
    category_id: UUID | None
    description: str | None
    merchant: str | None
    occurred_at: datetime
    source: TransactionSource
    receipt_image_url: str | None


class TransactionCategoryTotal(BaseModel):
    category_id: UUID | None
    category_name: str
    amount: Decimal
    percentage: Decimal


class TransactionRiskyCategory(BaseModel):
    slug: str
    label: str
    category_name: str
    budget: Decimal
    spent: Decimal
    remaining: Decimal
    used_percent: Decimal


class TransactionBudgetEnvelope(BaseModel):
    slug: str
    label: str
    category_name: str
    budget: Decimal
    spent: Decimal
    remaining: Decimal
    days_left_in_month: int
    safe_daily_amount: Decimal
    used_percent: Decimal | None
    status: Literal["safe", "watch", "over"]
    is_savings_goal: bool


class TransactionSummaryRead(BaseModel):
    period_start: datetime
    period_end: datetime
    income: Decimal
    expense: Decimal
    balance: Decimal
    previous_income: Decimal
    previous_expense: Decimal
    income_change_percent: Decimal | None
    expense_change_percent: Decimal | None
    category_totals: list[TransactionCategoryTotal]
    budgeted_month: Decimal
    spent_month: Decimal
    remaining_budget: Decimal
    risky_category: TransactionRiskyCategory | None
    envelopes: list[TransactionBudgetEnvelope]
