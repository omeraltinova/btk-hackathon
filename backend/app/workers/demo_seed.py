"""Seed the Yilmaz demo family for production and local demo runs."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from os import getenv
from uuid import UUID, uuid4

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
LEGACY_DENIZ_EMAILS: tuple[str, ...] = ()
LEGACY_ZEYNEP_EMAILS: tuple[str, ...] = ()
LEGACY_KEREM_EMAILS: tuple[str, ...] = ()


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


def deniz_email() -> str:
    return _env("DEMO_DENIZ_EMAIL", "deniz@demo.cuzdan-kocu.app")


def zeynep_email() -> str:
    return _env("DEMO_ZEYNEP_EMAIL", "zeynep@demo.cuzdan-kocu.app")


def kerem_email() -> str:
    return _env("DEMO_KEREM_EMAIL", "kerem@demo.cuzdan-kocu.app")


def child_demo_password() -> str:
    """Single shared demo password for the demo-only child accounts.

    Demo children (Elif, Deniz, Zeynep) keep their family-switch behavior in
    production via parent_id/family_id, but the seeder also gives them a known
    password so the login page demo selector can show each role from its own
    perspective. Real (non-demo) child accounts created at runtime still get
    password_hash=NULL — see `app/routers/family.py`.
    """
    return _env("DEMO_CHILD_PASSWORD", "demo123")


def individual_demo_password() -> str:
    return _env("DEMO_INDIVIDUAL_PASSWORD", "demo123")


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
    family_id: UUID | None = None,
    birth_date: date | None = None,
    finance_level: str = "beginner",
    password_hash: str | None = None,
    legacy_emails: tuple[str, ...] = (),
) -> User:
    user = _find_user_with_legacy(db, email, legacy_emails)
    if user is None:
        user = User(id=uuid4(), email=email, name=name, role=role)
        db.add(user)
    resolved_family_id = family_id
    if resolved_family_id is None and parent is not None:
        resolved_family_id = parent.family_id or parent.id
    if resolved_family_id is None and role == "parent":
        resolved_family_id = user.id
    user.email = email
    user.name = name
    user.role = role
    user.parent_id = parent.id if parent else None
    user.family_id = resolved_family_id
    user.password_hash = password_hash
    user.birth_date = birth_date
    user.finance_level = finance_level
    user.is_demo = True
    db.commit()
    db.refresh(user)
    return user


def _ensure_category(
    db: Session,
    *,
    user: User,
    name: str,
    icon: str,
    budget_monthly: str,
) -> None:
    category = db.execute(
        select(Category).where(Category.user_id == user.id, Category.name == name),
    ).scalar_one_or_none()
    if category is None:
        category = Category(user_id=user.id, name=name, icon=icon)
        db.add(category)
    category.icon = icon
    category.budget_monthly = Decimal(budget_monthly)


def _category_id(db: Session, name: str, user: User | None = None) -> UUID | None:
    if user is not None:
        category = db.execute(
            select(Category).where(Category.user_id == user.id, Category.name == name),
        ).scalar_one_or_none()
        if category is not None:
            return category.id
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
            category_id=_category_id(db, category_name, user),
            description=SEED_DESCRIPTION,
            merchant=merchant,
            occurred_at=datetime.now(UTC) - timedelta(days=days_ago),
            source=source,
            receipt_image_url=receipt_image_url,
            raw_ocr_data=raw_ocr_data,
        ),
    )


def _ensure_subscription(
    db: Session,
    *,
    user: User,
    name: str,
    merchant: str,
    amount: str,
    category_name: str,
    days_until_billing: int,
    billing_cycle: str = "monthly",
    recurrence_interval: int = 1,
    recurrence_unit: str = "month",
    usage_score: str = "0.80",
) -> None:
    existing = db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.name == name,
        ),
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        Subscription(
            user_id=user.id,
            name=name,
            merchant=merchant,
            amount=Decimal(amount),
            billing_cycle=billing_cycle,
            recurrence_interval=recurrence_interval,
            recurrence_unit=recurrence_unit,
            next_billing_date=(datetime.now(UTC) + timedelta(days=days_until_billing)).date(),
            category_id=_category_id(db, category_name, user),
            is_active=True,
            detected_from_transactions=False,
            usage_score=Decimal(usage_score),
        ),
    )


def seed_demo_family(db: Session) -> None:
    ayse = _upsert_user(
        db,
        email=parent_email(),
        name="Ayşe Yılmaz",
        role="parent",
        birth_date=date(1988, 3, 12),
        finance_level="beginner",
        password_hash=hash_password(parent_password()),
        legacy_emails=LEGACY_PARENT_EMAILS,
    )
    mehmet = _upsert_user(
        db,
        email=mehmet_email(),
        name="Mehmet Yılmaz",
        role="parent",
        family_id=ayse.family_id or ayse.id,
        birth_date=date(1984, 11, 6),
        finance_level="intermediate",
        password_hash=hash_password(mehmet_password()),
        legacy_emails=LEGACY_MEHMET_EMAILS,
    )
    # NOTE: demo children are intentionally given a password here so the login
    # page demo selector can show each perspective (e.g. minor-only kid mode UI,
    # adult child, individual). Non-demo child accounts created via /api/family
    # still use password_hash=None — see app/routers/family.py.
    elif_profile = _upsert_user(
        db,
        email=elif_email(),
        name="Elif Yılmaz",
        role="child",
        parent=ayse,
        birth_date=date(2014, 9, 5),
        finance_level="child",
        password_hash=hash_password(child_demo_password()),
        legacy_emails=LEGACY_ELIF_EMAILS,
    )
    deniz_profile = _upsert_user(
        db,
        email=deniz_email(),
        name="Deniz Yılmaz",
        role="child",
        parent=ayse,
        birth_date=date(2018, 4, 20),
        finance_level="child",
        password_hash=hash_password(child_demo_password()),
        legacy_emails=LEGACY_DENIZ_EMAILS,
    )
    zeynep_profile = _upsert_user(
        db,
        email=zeynep_email(),
        name="Zeynep Yılmaz",
        role="child",
        parent=ayse,
        birth_date=date(2004, 11, 18),
        finance_level="beginner",
        password_hash=hash_password(child_demo_password()),
        legacy_emails=LEGACY_ZEYNEP_EMAILS,
    )

    for name, icon, budget in (
        ("Market", "basket", "2800.00"),
        ("Fatura", "receipt", "1800.00"),
        ("Eğitim", "book", "2200.00"),
        ("Ulaşım", "bus", "1200.00"),
        ("Harçlık", "wallet", "600.00"),
        ("Birikim", "piggy-bank", "2500.00"),
    ):
        _ensure_category(db, user=ayse, name=name, icon=icon, budget_monthly=budget)
    db.flush()
    kerem_profile = _upsert_user(
        db,
        email=kerem_email(),
        name="Kerem Demir",
        role="individual",
        birth_date=date(2002, 6, 14),
        finance_level="intermediate",
        password_hash=hash_password(individual_demo_password()),
        legacy_emails=LEGACY_KEREM_EMAILS,
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
        user=ayse,
        amount="1200.00",
        tx_type="income",
        merchant="Bayram hediyesi",
        category_name="Hediye",
        days_ago=5,
    )
    _ensure_transaction(
        db,
        user=ayse,
        amount="449.90",
        tx_type="expense",
        merchant="TurkNet geçen ay",
        category_name="Fatura",
        days_ago=33,
        source="recurring",
    )
    _ensure_transaction(
        db,
        user=ayse,
        amount="499.90",
        tx_type="expense",
        merchant="TurkNet bu ay",
        category_name="Fatura",
        days_ago=4,
        source="recurring",
    )
    _ensure_transaction(
        db,
        user=ayse,
        amount="300.00",
        tx_type="expense",
        merchant="Elif harçlığı",
        category_name="Harçlık",
        days_ago=4,
    )
    _ensure_transaction(
        db,
        user=ayse,
        amount="620.00",
        tx_type="expense",
        merchant="Turkcell aile hattı",
        category_name="Telekom",
        days_ago=9,
    )
    _ensure_transaction(
        db,
        user=ayse,
        amount="1500.00",
        tx_type="expense",
        merchant="Birikim aktarımı",
        category_name="Birikim",
        days_ago=2,
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
        user=mehmet,
        amount="199.90",
        tx_type="expense",
        merchant="Netflix mart ödemesi",
        category_name="Eğlence",
        days_ago=70,
        source="recurring",
    )
    _ensure_transaction(
        db,
        user=mehmet,
        amount="229.90",
        tx_type="expense",
        merchant="Netflix nisan ödemesi",
        category_name="Eğlence",
        days_ago=36,
        source="recurring",
    )
    _ensure_transaction(
        db,
        user=mehmet,
        amount="1800.00",
        tx_type="expense",
        merchant="Opet yakıt",
        category_name="Akaryakıt",
        days_ago=10,
    )
    _ensure_transaction(
        db,
        user=elif_profile,
        amount="300.00",
        tx_type="income",
        merchant="Harçlık",
        category_name="Harçlık",
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
    _ensure_transaction(
        db,
        user=deniz_profile,
        amount="150.00",
        tx_type="income",
        merchant="Haftalık harçlık",
        category_name="Harçlık",
        days_ago=5,
    )
    _ensure_transaction(
        db,
        user=deniz_profile,
        amount="250.00",
        tx_type="income",
        merchant="Doğum günü hediyesi",
        category_name="Hediye",
        days_ago=8,
    )
    _ensure_transaction(
        db,
        user=deniz_profile,
        amount="38.50",
        tx_type="expense",
        merchant="Okul kantini",
        category_name="Eğitim",
        days_ago=2,
    )
    _ensure_transaction(
        db,
        user=zeynep_profile,
        amount="8500.00",
        tx_type="income",
        merchant="Staj ödemesi",
        category_name="Staj",
        days_ago=3,
    )
    _ensure_transaction(
        db,
        user=zeynep_profile,
        amount="1250.00",
        tx_type="expense",
        merchant="Üniversite kitapları",
        category_name="Eğitim",
        days_ago=1,
    )
    _ensure_transaction(
        db,
        user=zeynep_profile,
        amount="5600.00",
        tx_type="expense",
        merchant="Yurt geçen dönem",
        category_name="Eğitim",
        days_ago=95,
        source="recurring",
    )
    _ensure_subscription(
        db,
        user=ayse,
        name="Ev interneti",
        merchant="TurkNet",
        amount="499.90",
        category_name="Fatura",
        days_until_billing=5,
    )
    _ensure_subscription(
        db,
        user=mehmet,
        name="Netflix aile paketi",
        merchant="Netflix",
        amount="229.90",
        category_name="Eğlence",
        days_until_billing=7,
    )
    _ensure_subscription(
        db,
        user=zeynep_profile,
        name="Yurt ödemesi",
        merchant="Üniversite yurdu",
        amount="6000.00",
        category_name="Eğitim",
        days_until_billing=14,
        billing_cycle="custom",
        recurrence_interval=3,
        recurrence_unit="month",
        usage_score="1.00",
    )
    _ensure_transaction(
        db,
        user=kerem_profile,
        amount="32000.00",
        tx_type="income",
        merchant="İlk maaş",
        category_name="Maaş",
        days_ago=3,
    )
    _ensure_transaction(
        db,
        user=kerem_profile,
        amount="3450.00",
        tx_type="expense",
        merchant="Hepsiburada elektronik",
        category_name="Eğlence",
        days_ago=5,
    )
    _ensure_transaction(
        db,
        user=kerem_profile,
        amount="780.00",
        tx_type="expense",
        merchant="Yemeksepeti",
        category_name="Yemek",
        days_ago=2,
    )
    _ensure_transaction(
        db,
        user=kerem_profile,
        amount="49.99",
        tx_type="expense",
        merchant="Spotify geçen ay",
        category_name="Eğlence",
        days_ago=40,
        source="recurring",
    )
    _ensure_transaction(
        db,
        user=kerem_profile,
        amount="59.99",
        tx_type="expense",
        merchant="Spotify bu ay",
        category_name="Eğlence",
        days_ago=8,
        source="recurring",
    )
    _ensure_subscription(
        db,
        user=kerem_profile,
        name="Spotify Bireysel",
        merchant="Spotify",
        amount="59.99",
        category_name="Eğlence",
        days_until_billing=10,
        usage_score="0.95",
    )
    db.flush()
    refresh_insights_for_user(db, ayse)
    refresh_insights_for_user(db, mehmet)
    refresh_insights_for_user(db, kerem_profile)
    db.commit()


def main() -> None:
    with SessionLocal() as db:
        seed_demo_family(db)
    print("Demo family ready:")
    print(f"  - {parent_email()} (parent)")
    print(f"  - {mehmet_email()} (parent)")
    print(f"  - {elif_email()} (child / minor)")
    print(f"  - {deniz_email()} (child / minor)")
    print(f"  - {zeynep_email()} (child / adult)")
    print(f"  - {kerem_email()} (individual)")


if __name__ == "__main__":
    main()
