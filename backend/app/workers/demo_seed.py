"""Seed the Yilmaz demo family for production and local demo runs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from os import getenv
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db import SessionLocal
from app.models.category import Category
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.services.insights import refresh_insights_for_user

SEED_DESCRIPTION = "demo-family-seed"
LEGACY_PARENT_EMAILS = ("demo.aile@cuzdan-kocu.local",)
LEGACY_MEHMET_EMAILS = ("demo.mehmet@cuzdan-kocu.local",)
LEGACY_ELIF_EMAILS = ("demo.elif@cuzdan-kocu.local",)


def _env(name: str, default: str) -> str:
    return getenv(name) or default


def parent_email() -> str:
    return _env("DEMO_PARENT_EMAIL", "ayse@demo.cuzdan-kocu.app")


def parent_password() -> str:
    return _env("DEMO_PARENT_PASSWORD", "demo123")


def mehmet_email() -> str:
    return _env("DEMO_MEHMET_EMAIL", "mehmet@demo.cuzdan-kocu.app")


def mehmet_password() -> str:
    return _env("DEMO_MEHMET_PASSWORD", parent_password())


def elif_email() -> str:
    return _env("DEMO_ELIF_EMAIL", "elif@demo.cuzdan-kocu.app")


def _find_user(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def _find_user_with_legacy(db: Session, email: str, legacy_emails: tuple[str, ...]) -> User | None:
    user = _find_user(db, email)
    if user is not None:
        return user
    for legacy_email in legacy_emails:
        user = _find_user(db, legacy_email)
        if user is not None:
            return user
    return None


def _upsert_user(
    db: Session,
    *,
    email: str,
    name: str,
    role: str,
    parent: User | None = None,
    age: int | None = None,
    finance_level: str = "beginner",
    password_hash: str | None = None,
    legacy_emails: tuple[str, ...] = (),
) -> User:
    user = _find_user_with_legacy(db, email, legacy_emails)
    if user is None:
        user = User(email=email, name=name, role=role)
        db.add(user)
    user.email = email
    user.name = name
    user.role = role
    user.parent_id = parent.id if parent else None
    user.password_hash = password_hash
    user.age = age
    user.finance_level = finance_level
    user.is_demo = True
    db.commit()
    db.refresh(user)
    return user


def _category_id(db: Session, name: str) -> UUID | None:
    category = db.execute(
        select(Category).where(Category.user_id.is_(None), Category.name == name),
    ).scalar_one_or_none()
    return category.id if category else None


def _ensure_transaction(
    db: Session,
    *,
    user: User,
    amount: str,
    tx_type: str,
    merchant: str,
    category_name: str,
    days_ago: int,
    source: str = "manual",
    receipt_image_url: str | None = None,
    raw_ocr_data: dict[str, str] | None = None,
) -> None:
    existing = db.execute(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.merchant == merchant,
            Transaction.description == SEED_DESCRIPTION,
        ),
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        Transaction(
            user_id=user.id,
            amount=Decimal(amount),
            type=tx_type,
            category_id=_category_id(db, category_name),
            description=SEED_DESCRIPTION,
            merchant=merchant,
            occurred_at=datetime.now(UTC) - timedelta(days=days_ago),
            source=source,
            receipt_image_url=receipt_image_url,
            raw_ocr_data=raw_ocr_data,
        ),
    )


def _ensure_subscription(db: Session, *, user: User) -> None:
    existing = db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.name == "Ev interneti",
        ),
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        Subscription(
            user_id=user.id,
            name="Ev interneti",
            merchant="TurkNet",
            amount=Decimal("499.90"),
            billing_cycle="monthly",
            next_billing_date=(datetime.now(UTC) + timedelta(days=5)).date(),
            category_id=_category_id(db, "Fatura"),
            is_active=True,
            detected_from_transactions=False,
            usage_score=Decimal("0.80"),
        ),
    )


def seed_demo_family(db: Session) -> None:
    ayse = _upsert_user(
        db,
        email=parent_email(),
        name="Ayşe Yılmaz",
        role="parent",
        age=38,
        finance_level="beginner",
        password_hash=hash_password(parent_password()),
        legacy_emails=LEGACY_PARENT_EMAILS,
    )
    mehmet = _upsert_user(
        db,
        email=mehmet_email(),
        name="Mehmet Yılmaz",
        role="parent",
        age=42,
        finance_level="intermediate",
        password_hash=hash_password(mehmet_password()),
        legacy_emails=LEGACY_MEHMET_EMAILS,
    )
    elif_profile = _upsert_user(
        db,
        email=elif_email(),
        name="Elif Yılmaz",
        role="child",
        parent=ayse,
        age=12,
        finance_level="child",
        password_hash=None,
        legacy_emails=LEGACY_ELIF_EMAILS,
    )

    _ensure_transaction(
        db,
        user=ayse,
        amount="42000.00",
        tx_type="income",
        merchant="Ayşe maaşı",
        category_name="Maaş",
        days_ago=3,
    )
    _ensure_transaction(
        db,
        user=ayse,
        amount="1850.50",
        tx_type="expense",
        merchant="Migros haftalık market",
        category_name="Market",
        days_ago=2,
    )
    _ensure_transaction(
        db,
        user=ayse,
        amount="740.25",
        tx_type="expense",
        merchant="Geçen ay market",
        category_name="Market",
        days_ago=35,
    )
    _ensure_transaction(
        db,
        user=ayse,
        amount="247.50",
        tx_type="expense",
        merchant="Migros fişi",
        category_name="Market",
        days_ago=1,
        source="receipt_ocr",
        receipt_image_url="demo://migros-fisi",
        raw_ocr_data={"source": "demo_seed", "merchant": "Migros"},
    )
    _ensure_transaction(
        db,
        user=mehmet,
        amount="56000.00",
        tx_type="income",
        merchant="Mehmet maaşı",
        category_name="Maaş",
        days_ago=3,
    )
    _ensure_transaction(
        db,
        user=mehmet,
        amount="899.90",
        tx_type="expense",
        merchant="Netflix ve dijital servisler",
        category_name="Eğlence",
        days_ago=6,
    )
    _ensure_transaction(
        db,
        user=elif_profile,
        amount="300.00",
        tx_type="income",
        merchant="Harçlık",
        category_name="Maaş",
        days_ago=4,
    )
    _ensure_transaction(
        db,
        user=elif_profile,
        amount="45.00",
        tx_type="expense",
        merchant="Kırtasiye",
        category_name="Eğitim",
        days_ago=1,
    )
    _ensure_subscription(db, user=ayse)
    _ensure_subscription(db, user=mehmet)
    db.flush()
    refresh_insights_for_user(db, ayse)
    refresh_insights_for_user(db, mehmet)
    db.commit()


def main() -> None:
    with SessionLocal() as db:
        seed_demo_family(db)
    print(f"Demo family ready: {parent_email()}")


if __name__ == "__main__":
    main()
