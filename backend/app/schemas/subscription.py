from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

BillingCycle = Literal["weekly", "monthly", "yearly"]


class SubscriptionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    merchant: str | None = Field(default=None, max_length=120)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    billing_cycle: BillingCycle = "monthly"
    next_billing_date: date | None = None
    category_id: UUID | None = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Tekrarlayan ödeme adı boş olamaz.")
        return normalized

    @field_validator("merchant")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class SubscriptionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    merchant: str | None = Field(default=None, max_length=120)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    billing_cycle: BillingCycle | None = None
    next_billing_date: date | None = None
    category_id: UUID | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Tekrarlayan ödeme adı boş olamaz.")
        return normalized

    @field_validator("merchant")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class SubscriptionRead(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    merchant: str | None
    amount: Decimal
    billing_cycle: BillingCycle
    next_billing_date: date | None
    category_id: UUID | None
    is_active: bool
    detected_from_transactions: bool
    usage_score: Decimal | None
    monthly_equivalent: Decimal
