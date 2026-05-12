"""Seed a demo family for local hackathon runs.

Run from the backend directory:
    uv run python ../seeds/demo_family.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db import SessionLocal
from app.models.category import Category
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User

PARENT_EMAIL = "demo.aile@cuzdan-kocu.local"
PARENT_PASSWORD = "demo-sifre-123"


def _find_user(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


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
) -> User:
    user = _find_user(db, email)
    if user is None:
        user = User(email=email, name=name, role=role)
        db.add(user)
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
) -> None:
    existing = db.execute(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.merchant == merchant,
            Transaction.description == "demo-family-seed",
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
            description="demo-family-seed",
            merchant=merchant,
            occurred_at=datetime.now(UTC) - timedelta(days=days_ago),
            source="manual",
            receipt_image_url=None,
            raw_ocr_data=None,
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
    parent = _upsert_user(
        db,
        email=PARENT_EMAIL,
        name="Ayşe Yılmaz",
        role="parent",
        age=38,
        finance_level="beginner",
        password_hash=hash_password(PARENT_PASSWORD),
    )
    mehmet = _upsert_user(
        db,
        email="demo.mehmet@cuzdan-kocu.local",
        name="Mehmet Yılmaz",
        role="child",
        parent=parent,
        age=13,
        finance_level="child",
        password_hash=None,
    )
    elif_user = _upsert_user(
        db,
        email="demo.elif@cuzdan-kocu.local",
        name="Elif Yılmaz",
        role="child",
        parent=parent,
        age=10,
        finance_level="child",
        password_hash=None,
    )

    _ensure_transaction(
        db,
        user=parent,
        amount="42000.00",
        tx_type="income",
        merchant="Maaş",
        category_name="Maaş",
        days_ago=3,
    )
    _ensure_transaction(
        db,
        user=parent,
        amount="1850.50",
        tx_type="expense",
        merchant="Haftalık market",
        category_name="Market",
        days_ago=2,
    )
    _ensure_transaction(
        db,
        user=mehmet,
        amount="400.00",
        tx_type="income",
        merchant="Harçlık",
        category_name="Maaş",
        days_ago=4,
    )
    _ensure_transaction(
        db,
        user=mehmet,
        amount="70.00",
        tx_type="expense",
        merchant="Okul kantini",
        category_name="Eğitim",
        days_ago=1,
    )
    _ensure_transaction(
        db,
        user=elif_user,
        amount="300.00",
        tx_type="income",
        merchant="Harçlık",
        category_name="Maaş",
        days_ago=4,
    )
    _ensure_transaction(
        db,
        user=elif_user,
        amount="45.00",
        tx_type="expense",
        merchant="Kırtasiye",
        category_name="Eğitim",
        days_ago=1,
    )
    _ensure_subscription(db, user=parent)
    db.commit()
    print(f"Demo family ready: {PARENT_EMAIL} / {PARENT_PASSWORD}")


def main() -> None:
    with SessionLocal() as db:
        seed_demo_family(db)


if __name__ == "__main__":
    main()
