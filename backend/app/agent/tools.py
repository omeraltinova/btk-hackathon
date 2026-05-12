"""Agent tool implementations backed by scoped database queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.category import Category
from app.models.memory import AgentMemory
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.utils.date_format import format_tr_date
from app.utils.tl_format import format_tl

MONEY_QUANT = Decimal("0.01")
MAX_SPENDING_DAYS = 365


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _decimal_text(value: Decimal) -> str:
    return f"{_money(value):.2f}"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalized_days(days: int) -> int:
    return max(1, min(days, MAX_SPENDING_DAYS))


def _monthly_equivalent(amount: Decimal, billing_cycle: str) -> Decimal:
    if billing_cycle == "weekly":
        monthly = amount * Decimal("4")
    elif billing_cycle == "yearly":
        monthly = amount / Decimal("12")
    else:
        monthly = amount
    return _money(monthly)


def _load_current_user(db: Session, user_id: str) -> User:
    try:
        parsed_user_id = UUID(user_id)
    except ValueError as exc:
        raise ValueError("Geçersiz kullanıcı durumu.") from exc

    user = db.execute(select(User).where(User.id == parsed_user_id)).scalar_one_or_none()
    if user is None:
        raise ValueError("Kullanıcı bulunamadı.")
    return user


def visible_categories(db: Session, current_user: User) -> list[Category]:
    """Return system categories plus categories owned by the visible family scope."""
    user_ids = visible_user_ids(current_user)
    return list(
        db.execute(
            select(Category).where(or_(Category.user_id.in_(user_ids), Category.user_id.is_(None))),
        )
        .scalars()
        .all(),
    )


def infer_category_from_text(db: Session, current_user: User, text: str) -> str | None:
    """Best-effort category extraction for the deterministic Day 3 stream path."""
    normalized = text.casefold()
    categories = visible_categories(db, current_user)
    for category in sorted(categories, key=lambda item: len(item.name), reverse=True):
        if category.name.casefold() in normalized:
            return category.name
    return None


def build_spending_summary(
    db: Session,
    current_user: User,
    *,
    category: str | None = None,
    days: int = 30,
    now: datetime | None = None,
) -> dict[str, object]:
    """Summarise expenses for the current user's visible family scope."""
    safe_days = _normalized_days(days)
    period_end = _aware_utc(now or datetime.now(UTC))
    period_start = period_end - timedelta(days=safe_days)
    user_ids = visible_user_ids(current_user)
    categories = visible_categories(db, current_user)
    category_names = {item.id: item.name for item in categories}
    category_filter = category.casefold() if category else None

    transactions = list(
        db.execute(
            select(Transaction)
            .where(
                Transaction.user_id.in_(user_ids),
                Transaction.occurred_at >= period_start,
                Transaction.type == "expense",
            )
            .order_by(Transaction.occurred_at.desc()),
        )
        .scalars()
        .all(),
    )

    total = Decimal("0")
    included = 0
    category_totals: dict[str, Decimal] = {}
    latest_transaction: datetime | None = None

    for transaction in transactions:
        category_name = (
            category_names.get(transaction.category_id, "Kategorisiz")
            if transaction.category_id is not None
            else "Kategorisiz"
        )
        if category_filter is not None and category_filter not in category_name.casefold():
            continue
        amount = Decimal(transaction.amount)
        total += amount
        included += 1
        category_totals[category_name] = category_totals.get(category_name, Decimal("0")) + amount
        occurred_at = _aware_utc(transaction.occurred_at)
        if latest_transaction is None or occurred_at > latest_transaction:
            latest_transaction = occurred_at

    rows = [
        {
            "category": name,
            "amount": _decimal_text(amount),
            "amount_formatted": format_tl(amount),
        }
        for name, amount in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_start_formatted": format_tr_date(period_start),
        "period_end_formatted": format_tr_date(period_end),
        "days": safe_days,
        "category": category,
        "transaction_count": included,
        "total_amount": _decimal_text(total),
        "total_amount_formatted": format_tl(total),
        "latest_transaction_date": latest_transaction.isoformat() if latest_transaction else None,
        "latest_transaction_date_formatted": (
            format_tr_date(latest_transaction) if latest_transaction else None
        ),
        "category_totals": rows,
    }


def build_subscriptions_summary(
    db: Session,
    current_user: User,
    *,
    only_active: bool = True,
) -> dict[str, object]:
    """Return scoped subscriptions and their MVP monthly equivalent total."""
    query = select(Subscription).where(Subscription.user_id.in_(visible_user_ids(current_user)))
    if only_active:
        query = query.where(Subscription.is_active.is_(True))

    subscriptions = list(
        db.execute(query.order_by(Subscription.next_billing_date, Subscription.name))
        .scalars()
        .all(),
    )

    rows: list[dict[str, object]] = []
    monthly_total = Decimal("0")
    for subscription in subscriptions:
        monthly = _monthly_equivalent(Decimal(subscription.amount), subscription.billing_cycle)
        monthly_total += monthly
        rows.append(
            {
                "id": str(subscription.id),
                "name": subscription.name,
                "merchant": subscription.merchant,
                "amount": _decimal_text(Decimal(subscription.amount)),
                "amount_formatted": format_tl(Decimal(subscription.amount)),
                "billing_cycle": subscription.billing_cycle,
                "next_billing_date": (
                    subscription.next_billing_date.isoformat()
                    if subscription.next_billing_date
                    else None
                ),
                "next_billing_date_formatted": (
                    format_tr_date(subscription.next_billing_date)
                    if subscription.next_billing_date
                    else None
                ),
                "is_active": subscription.is_active,
                "usage_score": (
                    _decimal_text(Decimal(subscription.usage_score))
                    if subscription.usage_score is not None
                    else None
                ),
                "monthly_equivalent": _decimal_text(monthly),
                "monthly_equivalent_formatted": format_tl(monthly),
            },
        )

    return {
        "only_active": only_active,
        "count": len(rows),
        "monthly_total": _decimal_text(monthly_total),
        "monthly_total_formatted": format_tl(monthly_total),
        "subscriptions": rows,
    }


def build_user_memory(
    db: Session,
    current_user: User,
    *,
    key: str | None = None,
) -> dict[str, object]:
    """Return memory entries for the current user only."""
    query = select(AgentMemory).where(AgentMemory.user_id == current_user.id)
    if key is not None:
        query = query.where(AgentMemory.key == key)

    memories = list(db.execute(query.order_by(AgentMemory.key)).scalars().all())
    return {
        "key": key,
        "count": len(memories),
        "entries": [{"key": memory.key, "value": memory.value} for memory in memories],
    }


@tool("get_spending")
def get_spending_tool(
    category: str | None = None,
    days: int = 30,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Kullanıcının harcama özetini döner. `user_id` sistem durumundan gelir."""
    with SessionLocal() as db:
        return build_spending_summary(
            db,
            _load_current_user(db, user_id),
            category=category,
            days=days,
        )


@tool("get_subscriptions")
def get_subscriptions_tool(
    only_active: bool = True,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Kullanıcının abonelik ve tekrarlayan ödeme özetini döner."""
    with SessionLocal() as db:
        return build_subscriptions_summary(
            db,
            _load_current_user(db, user_id),
            only_active=only_active,
        )


@tool("get_user_memory")
def get_user_memory_tool(
    key: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Agent'in mevcut kullanıcı için hatırladığı bilgileri döner."""
    with SessionLocal() as db:
        return build_user_memory(db, _load_current_user(db, user_id), key=key)


TOOLS = [get_spending_tool, get_subscriptions_tool, get_user_memory_tool]
