from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.age import calculate_age

RegisterRole = Literal["parent", "individual"]
FinanceLevel = Literal["beginner", "intermediate", "advanced"]
AgeStatus = Literal["minor", "adult"]


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=120)
    role: RegisterRole = "individual"
    finance_level: FinanceLevel = "beginner"
    birth_date: date | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or "." not in email.rsplit("@", maxsplit=1)[-1]:
            raise ValueError("Geçerli bir e-posta adresi girin.")
        return email

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
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

    @model_validator(mode="after")
    def validate_adult_account(self) -> RegisterRequest:
        age = calculate_age(self.birth_date)
        if age is not None and age < 18:
            raise ValueError("Ebeveyn veya bireysel hesap için kullanıcı 18 yaşından büyük olmalı.")
        return self


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AccountUpdateRequest(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    birth_date: date | None = None
    finance_level: FinanceLevel | None = None
    current_password: str | None = Field(default=None, min_length=1, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip().lower()
        if "@" not in email or "." not in email.rsplit("@", maxsplit=1)[-1]:
            raise ValueError("Geçerli bir e-posta adresi girin.")
        return email

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

    @model_validator(mode="after")
    def validate_account_update(self) -> AccountUpdateRequest:
        if (self.current_password is None) != (self.new_password is None):
            raise ValueError("Şifre değiştirmek için mevcut ve yeni şifre birlikte gerekli.")
        age = calculate_age(self.birth_date)
        if age is not None and age < 18:
            raise ValueError("Hesap sahibi 18 yaşından büyük olmalı.")
        return self


class AccountDeleteRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class AuthUser(BaseModel):
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


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in_days: int
    user: AuthUser


class DemoAccount(BaseModel):
    """Public summary of a demo (is_demo=True) account for the login selector.

    The password is exposed here intentionally — these are shared demo
    credentials seeded by `app.workers.demo_seed`. The endpoint is restricted to
    accounts where `is_demo=True`, so real user passwords can never leak here.
    """

    email: str
    password: str
    name: str
    role: Literal["parent", "child", "individual"]
    age: int | None
    age_status: AgeStatus | None
    finance_level: Literal["beginner", "intermediate", "advanced", "child"]
    family_label: str | None
    tagline: str
