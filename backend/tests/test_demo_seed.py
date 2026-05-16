from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pytest import MonkeyPatch

from app.models.category import Category
from app.models.memory import AgentMemory
from app.models.saving_goal import SavingGoal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.workers.demo_seed import seed_demo_family


class FakeScalars:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return self._items


class FakeResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def scalar_one_or_none(self) -> object | None:
        return self._items[0] if self._items else None

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._items)


class FakeSession:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.transactions: list[Transaction] = []
        self.subscriptions: list[Subscription] = []
        self.saving_goals: list[SavingGoal] = []
        self.memories: list[AgentMemory] = []
        self.categories = [
            Category(id=uuid4(), user_id=None, name="Market", icon="basket", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Maaş", icon="wallet", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Fatura", icon="receipt", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Eğitim", icon="book", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Eğlence", icon="ticket", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Harçlık", icon="piggy-bank", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Staj", icon="briefcase", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Hediye", icon="gift", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Akaryakıt", icon="fuel", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Telekom", icon="phone", parent_id=None),
            Category(id=uuid4(), user_id=None, name="Yemek", icon="utensils", parent_id=None),
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
        elif entity is SavingGoal:
            rows = self.saving_goals
        elif entity is AgentMemory:
            rows = self.memories
        else:
            rows = []
        return FakeResult([row for row in rows if self._matches_statement(statement, row)])

    def add(
        self,
        row: User | Transaction | Subscription | SavingGoal | AgentMemory | Category,
    ) -> None:
        if row.id is None:
            row.id = uuid4()
        if isinstance(row, User):
            self.users.append(row)
        elif isinstance(row, Transaction):
            self.transactions.append(row)
        elif isinstance(row, Category):
            self.categories.append(row)
        elif isinstance(row, SavingGoal):
            self.saving_goals.append(row)
        elif isinstance(row, AgentMemory):
            self.memories.append(row)
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
            if column_name == "id" and getattr(row, "id", None) != value:
                return False
            if column_name == "user_id" and getattr(row, "user_id", None) != value:
                return False
            if column_name == "merchant" and getattr(row, "merchant", None) != value:
                return False
            if column_name == "description" and getattr(row, "description", None) != value:
                return False
            if column_name == "goal_type" and getattr(row, "goal_type", None) != value:
                return False
            if column_name == "title" and getattr(row, "title", None) != value:
                return False
            if column_name == "key" and getattr(row, "key", None) != value:
                return False
            if column_name == "category_id" and getattr(row, "category_id", None) != value:
                return False
            if column_name == "type" and getattr(row, "type", None) != value:
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
    assert users_by_name["Deniz Yılmaz"].role == "child"
    assert users_by_name["Zeynep Yılmaz"].role == "child"
    assert users_by_name["Kerem Demir"].role == "individual"
    assert users_by_name["Elif Yılmaz"].parent_id == users_by_name["Ayşe Yılmaz"].id
    assert users_by_name["Zeynep Yılmaz"].age_status == "adult"
    assert users_by_name["Deniz Yılmaz"].age_status == "minor"
    assert users_by_name["Ayşe Yılmaz"].family_id == users_by_name["Mehmet Yılmaz"].family_id
    # Kerem is independent of the Yılmaz family.
    assert users_by_name["Kerem Demir"].parent_id is None
    assert users_by_name["Kerem Demir"].family_id is None
    # Demo seeder gives every demo account a password so each role can be
    # demonstrated from its own perspective via the login selector. Real
    # non-demo child accounts created at runtime still get password_hash=None.
    assert all(user.password_hash is not None for user in db.users)
    assert all(user.is_demo for user in db.users)
    assert len(db.users) == 6
    assert len(db.transactions) == 28
    assert any(transaction.source == "receipt_ocr" for transaction in db.transactions)
    assert any(transaction.source == "recurring" for transaction in db.transactions)
    assert any(transaction.merchant == "Bayram hediyesi" for transaction in db.transactions)
    assert any(transaction.merchant == "Elif harçlığı" for transaction in db.transactions)
    assert any(transaction.merchant == "Birikim aktarımı" for transaction in db.transactions)
    assert any(
        category.user_id == users_by_name["Ayşe Yılmaz"].id
        and category.name == "Birikim"
        and str(category.budget_monthly) == "2500.00"
        for category in db.categories
    )
    assert len(db.subscriptions) == 4
    assert any(subscription.billing_cycle == "custom" for subscription in db.subscriptions)
    assert len(db.saving_goals) == 4
    assert {(goal.user_id, goal.goal_type, goal.title) for goal in db.saving_goals} == {
        (users_by_name["Ayşe Yılmaz"].id, "accumulation", "Yaz tatili birikimi"),
        (users_by_name["Ayşe Yılmaz"].id, "expense_reduction", "Market harcamamı azalt"),
        (users_by_name["Mehmet Yılmaz"].id, "accumulation", "Acil durum fonu"),
        (users_by_name["Mehmet Yılmaz"].id, "expense_reduction", "Eğlence harcamamı azalt"),
    }
    assert len(db.memories) == 4
    assert {(memory.user_id, memory.key) for memory in db.memories} == {
        (users_by_name["Ayşe Yılmaz"].id, "hedef"),
        (users_by_name["Ayşe Yılmaz"].id, "tercih"),
        (users_by_name["Mehmet Yılmaz"].id, "hedef"),
        (users_by_name["Mehmet Yılmaz"].id, "abonelik_odagi"),
    }
    assert [user.name for user in db.refreshed_users] == [
        "Ayşe Yılmaz",
        "Mehmet Yılmaz",
        "Kerem Demir",
        "Ayşe Yılmaz",
        "Mehmet Yılmaz",
        "Kerem Demir",
    ]
