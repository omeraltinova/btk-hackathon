from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import create_token, verify_token
from app.db import get_db
from app.main import app
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User


class FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalar_one_or_none(self) -> Any | None:
        return self._items[0] if self._items else None

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._items)


class FakeSession:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.transactions: list[Transaction] = []
        self.subscriptions: list[Subscription] = []

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is not User:
            if entity is Transaction:
                return FakeResult(
                    [
                        transaction
                        for transaction in self.transactions
                        if self._matches_user_scoped_row(statement, transaction.user_id)
                    ],
                )
            if entity is Subscription:
                return FakeResult(
                    [
                        subscription
                        for subscription in self.subscriptions
                        if self._matches_user_scoped_row(statement, subscription.user_id)
                    ],
                )
            return FakeResult([])
        return FakeResult([user for user in self.users if self._matches_user(statement, user)])

    def add(self, user: User) -> None:
        if user.id is None:
            user.id = uuid4()
        self._ensure_timestamps(user)
        self.users.append(user)

    def commit(self) -> None:
        return None

    def refresh(self, user: User) -> None:
        if user.id is None:
            user.id = uuid4()
        self._ensure_timestamps(user)

    def delete(self, user: User) -> None:
        self.users = [item for item in self.users if item.id != user.id]

    @staticmethod
    def _matches_user(statement: object, user: User) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "id" and user.id != value:
                return False
            if column_name == "parent_id" and user.parent_id != value:
                return False
            if column_name == "family_id" and user.family_id != value:
                return False
            if column_name == "role" and isinstance(value, list | tuple | set):
                return user.role in value
            if column_name == "role" and user.role != value:
                return False
        return True

    @staticmethod
    def _matches_user_scoped_row(statement: object, user_id: UUID) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "user_id" and isinstance(value, list | tuple | set):
                return user_id in value
        return True

    @staticmethod
    def _ensure_timestamps(user: User) -> None:
        now = datetime.now(UTC)
        if getattr(user, "created_at", None) is None:
            user.created_at = now
        if getattr(user, "updated_at", None) is None:
            user.updated_at = now


@pytest.fixture
def fake_session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(fake_session: FakeSession) -> Iterator[TestClient]:
    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(
    *,
    role: str = "parent",
    name: str = "Ayşe Yılmaz",
    parent_id: UUID | None = None,
) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        name=name,
        role=role,
        parent_id=parent_id,
        password_hash=None if role == "child" else "hash",
        birth_date=date(2014, 1, 1) if role == "child" else date(1988, 1, 1),
        finance_level="child" if role == "child" else "beginner",
        is_demo=True,
    )
    user.children = []
    user.created_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    user.updated_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    return user


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(user.id)}"}


def make_transaction(
    user: User,
    *,
    amount: str,
    tx_type: str,
    merchant: str = "Test",
    occurred_at: datetime | None = None,
    source: str = "manual",
) -> Transaction:
    return Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal(amount),
        type=tx_type,
        category_id=None,
        description="Aile özeti testi",
        merchant=merchant,
        occurred_at=occurred_at or datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
        source=source,
        receipt_image_url=None,
        raw_ocr_data=None,
    )


def make_subscription(user: User, *, amount: str, cycle: str = "monthly") -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user.id,
        name="Ev interneti",
        merchant="TurkNet",
        amount=Decimal(amount),
        billing_cycle=cycle,
        recurrence_interval=1,
        recurrence_unit={"weekly": "week", "yearly": "year"}.get(cycle, "month"),
        next_billing_date=date(2026, 5, 18),
        category_id=None,
        is_active=True,
        detected_from_transactions=False,
        usage_score=None,
    )


def test_parent_can_create_list_update_and_switch_child(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    parent = make_user()
    fake_session.users.append(parent)

    create_response = client.post(
        "/api/family/children",
        headers=auth_header(parent),
        json={"name": "  Mehmet   Yılmaz ", "birth_date": "2015-01-01", "finance_level": "child"},
    )

    assert create_response.status_code == 201
    child_body = create_response.json()
    assert child_body["name"] == "Mehmet Yılmaz"
    assert child_body["role"] == "child"
    assert child_body["birth_date"] == "2015-01-01"
    assert child_body["age_status"] == "minor"
    created_child = fake_session.users[1]
    assert created_child.password_hash is None
    assert created_child.parent_id == parent.id

    list_response = client.get("/api/family", headers=auth_header(parent))
    assert list_response.status_code == 200
    assert [member["role"] for member in list_response.json()] == ["parent", "child"]

    patch_response = client.patch(
        f"/api/family/children/{created_child.id}",
        headers=auth_header(parent),
        json={"birth_date": "2014-01-01"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["birth_date"] == "2014-01-01"
    assert patch_response.json()["age"] is not None

    switch_response = client.post(
        f"/api/family/switch/{created_child.id}",
        headers=auth_header(parent),
    )
    assert switch_response.status_code == 200
    body = switch_response.json()
    assert body["user"]["id"] == str(created_child.id)
    assert body["user"]["role"] == "child"
    assert verify_token(body["access_token"])["sub"] == str(created_child.id)


def test_parent_can_delete_child_profile(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    parent = make_user()
    child = make_user(role="child", name="Elif Yılmaz", parent_id=parent.id)
    fake_session.users.extend([parent, child])

    response = client.delete(
        f"/api/family/children/{child.id}",
        headers=auth_header(parent),
    )

    assert response.status_code == 204
    assert [user.id for user in fake_session.users] == [parent.id]


def test_parent_can_create_adult_child_relationship(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    parent = make_user()
    fake_session.users.append(parent)

    response = client.post(
        "/api/family/children",
        headers=auth_header(parent),
        json={
            "name": "Zeynep Yılmaz",
            "birth_date": "2004-11-18",
            "finance_level": "beginner",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "child"
    assert body["age_status"] == "adult"
    assert body["finance_level"] == "beginner"


def test_child_cannot_manage_family(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    parent = make_user()
    child = make_user(role="child", name="Elif Yılmaz", parent_id=parent.id)
    fake_session.users.extend([parent, child])

    response = client.post(
        "/api/family/children",
        headers=auth_header(child),
        json={"name": "Yeni Profil", "birth_date": "2016-01-01", "finance_level": "child"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Aile yönetimi için ebeveyn hesabı gerekli."


def test_parent_can_read_family_financial_overview(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    parent = make_user()
    child = make_user(role="child", name="Elif Yılmaz", parent_id=parent.id)
    fake_session.users.extend([parent, child])
    fake_session.transactions.extend(
        [
            make_transaction(parent, amount="1000.00", tx_type="income"),
            make_transaction(
                parent,
                amount="250.00",
                tx_type="expense",
                merchant="Migros",
                occurred_at=datetime(2026, 5, 13, 13, 0, tzinfo=UTC),
                source="receipt_ocr",
            ),
            make_transaction(child, amount="45.00", tx_type="expense", merchant="Kırtasiye"),
        ],
    )
    fake_session.subscriptions.append(make_subscription(parent, amount="100.00"))

    response = client.get("/api/family/overview", headers=auth_header(parent))

    assert response.status_code == 200
    body = response.json()
    assert body["total_income"] == "1000.00"
    assert body["total_expense"] == "295.00"
    assert body["total_balance"] == "705.00"
    assert body["total_recurring_monthly"] == "100.00"
    assert [member["name"] for member in body["members"]] == ["Ayşe Yılmaz", "Elif Yılmaz"]
    parent_row = body["members"][0]
    child_row = body["members"][1]
    assert parent_row["expense_share_percent"] == "84.75"
    assert parent_row["receipt_transaction_count"] == 1
    assert parent_row["recurring_count"] == 1
    assert parent_row["latest_transaction_merchant"] == "Migros"
    assert parent_row["latest_transaction_amount"] == "250.00"
    assert parent_row["latest_transaction_type"] == "expense"
    assert child_row["expense_share_percent"] == "15.25"
    assert child_row["recurring_count"] == 0


def test_child_cannot_read_family_financial_overview(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    parent = make_user()
    child = make_user(role="child", name="Elif Yılmaz", parent_id=parent.id)
    fake_session.users.extend([parent, child])

    response = client.get("/api/family/overview", headers=auth_header(child))

    assert response.status_code == 403
    assert response.json()["detail"] == "Aile yönetimi için ebeveyn hesabı gerekli."
