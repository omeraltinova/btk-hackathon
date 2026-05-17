"""Tests for the POST /api/recurring/materialize endpoint."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.routers.recurring import materialize


class FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._items)


class FakeSession:
    def __init__(
        self,
        *,
        subscriptions: list[Subscription],
        today: date,
    ) -> None:
        self.subscriptions = subscriptions
        self.transactions: list[Transaction] = []
        self.today = today
        self.commits = 0

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is Subscription:
            scope = self._scope_user_ids(statement)
            return FakeResult(
                [
                    subscription
                    for subscription in self.subscriptions
                    if subscription.user_id in scope
                    and subscription.is_active
                    and subscription.next_billing_date is not None
                    and subscription.next_billing_date <= self.today
                ],
            )
        if entity is Transaction:
            return FakeResult([])
        return FakeResult([])

    def add(self, row: Transaction) -> None:
        if row.id is None:
            row.id = uuid4()
        self.transactions.append(row)

    def commit(self) -> None:
        self.commits += 1

    @staticmethod
    def _scope_user_ids(statement: object) -> set[UUID]:
        for criterion in getattr(statement, "_where_criteria", ()):
            for clause in getattr(criterion, "clauses", [criterion]):
                right = getattr(clause, "right", None)
                value = getattr(right, "value", None)
                if isinstance(value, list | tuple | set) and value:
                    return {UUID(str(v)) if not isinstance(v, UUID) else v for v in value}
        return set()


def make_user() -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        name="Test",
        role="individual",
        parent_id=None,
        password_hash="hash",
        birth_date=date(1990, 1, 1),
        finance_level="beginner",
        is_demo=False,
    )
    user.children = []
    return user


def make_subscription(*, next_billing_date: date, user_id: UUID) -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user_id,
        name="Ev interneti",
        merchant="TurkNet",
        amount=Decimal("499.90"),
        type="expense",
        billing_cycle="monthly",
        recurrence_interval=1,
        recurrence_unit="month",
        next_billing_date=next_billing_date,
        category_id=None,
        is_active=True,
        detected_from_transactions=False,
        usage_score=None,
    )


def test_materialize_endpoint_returns_created_count(monkeypatch: Any) -> None:
    """The endpoint forwards to the materializer and reports the count it returns."""
    user = make_user()
    today = datetime.now().date()
    subscription = make_subscription(next_billing_date=today, user_id=user.id)
    db = FakeSession(subscriptions=[subscription], today=today)

    response = materialize(db=db, current_user=user)  # type: ignore[arg-type]

    assert response.created == 1
    assert db.commits >= 1
    assert len(db.transactions) == 1


def test_materialize_endpoint_returns_zero_when_nothing_due() -> None:
    user = make_user()
    today = datetime.now().date()
    db = FakeSession(subscriptions=[], today=today)

    response = materialize(db=db, current_user=user)  # type: ignore[arg-type]

    assert response.created == 0
