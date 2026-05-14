from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

SavingGoalStatus = Literal["active", "completed", "paused"]
SavingGoalCreator = Literal["manual", "agent"]
SavingGoalProgressStatus = Literal["on_track", "at_risk", "over_limit", "completed"]


class SavingGoalCreate(BaseModel):
    category_id: UUID | None = None
    category_name: str | None = Field(default=None, min_length=2, max_length=80)
    title: str | None = Field(default=None, max_length=120)
    target_reduction_percent: Decimal = Field(
        default=Decimal("15"),
        ge=1,
        le=50,
        max_digits=5,
        decimal_places=2,
    )
    baseline_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    @field_validator("category_name", "title")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @model_validator(mode="after")
    def require_category(self) -> SavingGoalCreate:
        if self.category_id is None and self.category_name is None:
            raise ValueError("Kategori seçmelisin.")
        return self


class SavingGoalRead(BaseModel):
    id: UUID
    user_id: UUID
    category_id: UUID | None
    category_name: str
    title: str
    baseline_amount: Decimal
    target_spending_amount: Decimal
    target_saving_amount: Decimal
    start_date: datetime
    end_date: datetime
    status: SavingGoalStatus
    strategy: dict[str, Any] | None
    created_by: SavingGoalCreator


class SavingGoalProgressRead(BaseModel):
    goal: SavingGoalRead
    actual_spending: Decimal
    saved_amount: Decimal
    remaining_limit: Decimal
    progress_percent: Decimal
    expected_spending_to_date: Decimal
    status_label: SavingGoalProgressStatus
    tactics: list[str]
