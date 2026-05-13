from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.services.recurring_materializer import materialize_due_subscriptions, next_recurrence_date


class FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._items

    def scalar_one_or_none(self) -> Any | None:
        return self._items[0] if self._items else None


class FakeSession:
    def __init__(self, subscriptions: list[Subscription], today: date) -> None:
        self.subscriptions = subscriptions
        self.transactions: list[Transaction] = []
        self.today = today
        self.commits = 0

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        name = descriptions[0].get("name") if descriptions else None
        if entity is Subscription:
            return FakeResult(
                [
                    subscription
                    for subscription in self.subscriptions
                    if subscription.is_active
                    and subscription.next_billing_date is not None
                    and subscription.next_billing_date <= self.today
                ],
            )
        if entity is Transaction or name == "id":
            return FakeResult(self.transactions)
        return FakeResult([])

    def add(self, row: Transaction) -> None:
        if row.id is None:
            row.id = uuid4()
        self.transactions.append(row)

    def commit(self) -> None:
        self.commits += 1


def make_subscription(
    *,
    next_billing_date: date,
    user_id: object | None = None,
    name: str = "Ev interneti",
) -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user_id or uuid4(),
        name=name,
        merchant="TurkNet",
        amount=Decimal("499.90"),
        billing_cycle="monthly",
        recurrence_interval=1,
        recurrence_unit="month",
        next_billing_date=next_billing_date,
        category_id=None,
        is_active=True,
        detected_from_transactions=False,
        usage_score=None,
    )


def test_next_recurrence_date_clamps_month_end() -> None:
    assert next_recurrence_date(date(2026, 1, 31), 1, "month") == date(2026, 2, 28)
    assert next_recurrence_date(date(2026, 2, 28), 1, "year") == date(2027, 2, 28)


def test_materialize_due_subscription_posts_expense_and_advances_date() -> None:
    subscription = make_subscription(next_billing_date=date(2026, 5, 13))
    db = FakeSession([subscription], today=date(2026, 5, 13))

    created = materialize_due_subscriptions(
        db,  # type: ignore[arg-type]
        [subscription.user_id],
        today=date(2026, 5, 13),
    )

    assert created == 1
    assert db.commits == 1
    assert subscription.next_billing_date == date(2026, 6, 13)
    assert len(db.transactions) == 1
    transaction = db.transactions[0]
    assert transaction.user_id == subscription.user_id
    assert transaction.type == "expense"
    assert transaction.source == "recurring"
    assert transaction.amount == Decimal("499.90")
    assert transaction.merchant == "TurkNet"
    assert transaction.occurred_at == datetime(2026, 5, 13, 9, 0, tzinfo=UTC)


def test_materialize_due_subscriptions_keeps_same_merchant_subscriptions_distinct() -> None:
    user_id = uuid4()
    first = make_subscription(next_billing_date=date(2026, 5, 13), user_id=user_id)
    second = make_subscription(
        next_billing_date=date(2026, 5, 13),
        user_id=user_id,
        name="Yedek internet hattı",
    )
    db = FakeSession([first, second], today=date(2026, 5, 13))

    created = materialize_due_subscriptions(
        db,  # type: ignore[arg-type]
        [user_id],
        today=date(2026, 5, 13),
    )

    assert created == 2
    assert len(db.transactions) == 2
    subscription_ids = {
        transaction.raw_ocr_data.get("subscription_id")
        for transaction in db.transactions
        if isinstance(transaction.raw_ocr_data, dict)
    }
    assert subscription_ids == {str(first.id), str(second.id)}
