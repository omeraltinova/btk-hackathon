"""Materialize due recurring subscriptions as expense transactions."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.transaction import Transaction

ISTANBUL = ZoneInfo("Europe/Istanbul")


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = (month_index % 12) + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def next_recurrence_date(value: date, interval: int | None, unit: str | None) -> date:
    safe_interval = max(interval or 1, 1)
    if unit == "day":
        return value + timedelta(days=safe_interval)
    if unit == "week":
        return value + timedelta(weeks=safe_interval)
    if unit == "year":
        return _add_months(value, safe_interval * 12)
    return _add_months(value, safe_interval)


def _local_noon_utc(value: date) -> datetime:
    return datetime.combine(value, time(12, 0), tzinfo=ISTANBUL).astimezone(UTC)


def _local_day_bounds_utc(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min, tzinfo=ISTANBUL).astimezone(UTC)
    end = datetime.combine(value + timedelta(days=1), time.min, tzinfo=ISTANBUL).astimezone(UTC)
    return start, end


def _recurring_transaction_exists(db: Session, subscription: Subscription, due_date: date) -> bool:
    start, end = _local_day_bounds_utc(due_date)
    existing_transactions = (
        db.execute(
            select(Transaction).where(
                Transaction.user_id == subscription.user_id,
                Transaction.source == "recurring",
                Transaction.occurred_at >= start,
                Transaction.occurred_at < end,
            ),
        )
        .scalars()
        .all()
    )
    subscription_id = str(subscription.id)
    billing_date = due_date.isoformat()
    return any(
        isinstance(transaction.raw_ocr_data, dict)
        and transaction.raw_ocr_data.get("subscription_id") == subscription_id
        and transaction.raw_ocr_data.get("billing_date") == billing_date
        for transaction in existing_transactions
    )


def materialize_due_subscriptions(
    db: Session,
    user_ids: list[UUID],
    *,
    today: date | None = None,
) -> int:
    """Create expense transactions for active subscriptions due up to today."""

    if not user_ids:
        return 0
    local_today = today or datetime.now(ISTANBUL).date()
    subscriptions = (
        db.execute(
            select(Subscription).where(
                Subscription.user_id.in_(user_ids),
                Subscription.is_active.is_(True),
                Subscription.next_billing_date.is_not(None),
                Subscription.next_billing_date <= local_today,
            ).with_for_update(skip_locked=True),
        )
        .scalars()
        .all()
    )

    created_count = 0
    advanced_count = 0
    for subscription in subscriptions:
        due_date = subscription.next_billing_date
        if due_date is None:
            continue
        while due_date <= local_today:
            if not _recurring_transaction_exists(db, subscription, due_date):
                db.add(
                    Transaction(
                        user_id=subscription.user_id,
                        amount=Decimal(subscription.amount),
                        type="expense",
                        category_id=subscription.category_id,
                        description="Tekrarlayan ödeme",
                        merchant=subscription.merchant or subscription.name,
                        occurred_at=_local_noon_utc(due_date),
                        source="recurring",
                        receipt_image_url=None,
                        raw_ocr_data={
                            "source": "recurring_materializer",
                            "subscription_id": str(subscription.id),
                            "billing_date": due_date.isoformat(),
                        },
                    ),
                )
                created_count += 1
            due_date = next_recurrence_date(
                due_date,
                subscription.recurrence_interval,
                subscription.recurrence_unit,
            )
        if subscription.next_billing_date != due_date:
            subscription.next_billing_date = due_date
            advanced_count += 1

    if created_count > 0 or advanced_count > 0:
        db.commit()
    return created_count
