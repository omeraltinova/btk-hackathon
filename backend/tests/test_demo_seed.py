from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pytest import MonkeyPatch

from app.models.category import Category
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.workers.demo_seed import seed_demo_family


class FakeResult:
    def __init__(self, item: object | None) -> None:
        self._item = item

    def scalar_one_or_none(self) -> object | None:
        return self._item


class FakeSession:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.transactions: list[Transaction] = []
        self.subscriptions: list[Subscription] = []
        self.categories = [
            Category(id=uuid4(), user_id=None, name="Market", icon="basket", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Maaş", icon="wallet", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Fatura", icon="receipt", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Eğitim", icon="book", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Eğlence", icon="ticket", parent_id=None),
        ]
        self.refreshed_users: list[User] = []

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        rows: list[Any]
        if entity is User:
            rows = self.users
        elif entity is Category:
            rows = self.categories
        elif entity is Transaction:
            rows = self.transactions
        elif entity is Subscription:
            rows = self.subscriptions
        else:
            rows = []
        return FakeResult(
            next((row for row in rows if self._matches_statement(statement, row)), None)
        )

    def add(self, row: User | Transaction | Subscription) -> None:
        if row.id is None:
            row.id = uuid4()
        if isinstance(row, User):
            self.users.append(row)
        elif isinstance(row, Transaction):
            self.transactions.append(row)
        else:
            self.subscriptions.append(row)

    def commit(self) -> None:
        return None

    def flush(self) -> None:
        return None

    def refresh(self, row: User) -> None:
        if row.id is None:
            row.id = uuid4()
        if getattr(row, "created_at", None) is None:
            row.created_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
        if getattr(row, "updated_at", None) is None:
            row.updated_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)

    @staticmethod
    def _matches_statement(statement: object, row: object) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):  # pragma: no branch
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "email" and getattr(row, "email", None) != value:
                return False
            if column_name == "name" and getattr(row, "name", None) != value:
                return False
            if column_name == "user_id" and getattr(row, "user_id", None) != value:
                return False
            if column_name == "merchant" and getattr(row, "merchant", None) != value:
                return False
            if column_name == "description" and getattr(row, "description", None) != value:
                return False
        return True


def test_demo_seed_creates_parent_logins_child_and_refreshes_insights(
    monkeypatch: MonkeyPatch,
) -> None:
    db = FakeSession()

    def fake_refresh(session: FakeSession, user: User) -> list[object]:
        assert session is db
        session.refreshed_users.append(user)
        return []

    monkeypatch.setattr("app.workers.demo_seed.refresh_insights_for_user", fake_refresh)

    seed_demo_family(db)  # type: ignore[arg-type]
    seed_demo_family(db)  # idempotency smoke check

    users_by_name = {user.name: user for user in db.users}
    assert users_by_name["Ayşe Yılmaz"].role == "parent"
    assert users_by_name["Mehmet Yılmaz"].role == "parent"
    assert users_by_name["Elif Yılmaz"].role == "child"
    assert users_by_name["Elif Yılmaz"].parent_id == users_by_name["Ayşe Yılmaz"].id
    assert all(user.is_demo for user in db.users)
    assert len(db.users) == 3
    assert len(db.transactions) == 8
    assert any(transaction.source == "receipt_ocr" for transaction in db.transactions)
    assert len(db.subscriptions) == 2
    assert [user.name for user in db.refreshed_users] == [
        "Ayşe Yılmaz",
        "Mehmet Yılmaz",
        "Ayşe Yılmaz",
        "Mehmet Yılmaz",
    ]
