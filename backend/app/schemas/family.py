from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.age import calculate_age

FamilyFinanceLevel = Literal["child", "beginner", "intermediate", "advanced"]
AgeStatus = Literal["minor", "adult"]


class FamilyMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: Literal["parent", "child", "individual"]
    parent_id: UUID | None
    family_id: UUID | None
    birth_date: date | None
    age: int | None
    age_status: AgeStatus | None
    finance_level: Literal["beginner", "intermediate", "advanced", "child"]
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class FamilyMemberFinanceRead(BaseModel):
    user_id: UUID
    name: str
    role: Literal["parent", "child"]
    birth_date: date | None
    age: int | None
    age_status: AgeStatus | None
    income: Decimal
    expense: Decimal
    balance: Decimal
    expense_share_percent: Decimal
    recurring_monthly: Decimal
    recurring_count: int
    transaction_count: int
    receipt_transaction_count: int
    latest_transaction_at: datetime | None
    latest_transaction_merchant: str | None
    latest_transaction_amount: Decimal | None
    latest_transaction_type: Literal["income", "expense"] | None


class FamilyOverviewRead(BaseModel):
    period_start: datetime
    period_end: datetime
    total_income: Decimal
    total_expense: Decimal
    total_balance: Decimal
    total_recurring_monthly: Decimal
    members: list[FamilyMemberFinanceRead]


class ChildCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    birth_date: date
    finance_level: FamilyFinanceLevel = "child"

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Doğum tarihi gelecekte olamaz.")
        age = calculate_age(value)
        if age is not None and age > 120:
            raise ValueError("Doğum tarihi geçerli görünmüyor.")
        return value


class ChildUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    birth_date: date | None = None
    finance_level: FamilyFinanceLevel | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return None
        if value > date.today():
            raise ValueError("Doğum tarihi gelecekte olamaz.")
        age = calculate_age(value)
        if age is not None and age > 120:
            raise ValueError("Doğum tarihi geçerli görünmüyor.")
        return value
