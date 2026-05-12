from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChildFinanceLevel = Literal["child", "beginner"]


class FamilyMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: Literal["parent", "child", "individual"]
    parent_id: UUID | None
    age: int | None
    finance_level: Literal["beginner", "intermediate", "advanced", "child"]
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class ChildCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=5, le=17)
    finance_level: ChildFinanceLevel = "child"

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class ChildUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    age: int | None = Field(default=None, ge=5, le=17)
    finance_level: ChildFinanceLevel | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())
