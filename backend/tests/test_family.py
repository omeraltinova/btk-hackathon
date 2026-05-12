from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import create_token, verify_token
from app.db import get_db
from app.main import app
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

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is not User:
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

    @staticmethod
    def _matches_user(statement: object, user: User) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "id" and user.id != value:
                return False
            if column_name == "parent_id" and user.parent_id != value:
                return False
            if column_name == "role" and user.role != value:
                return False
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
        age=12 if role == "child" else 38,
        finance_level="child" if role == "child" else "beginner",
        is_demo=True,
    )
    user.children = []
    user.created_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    user.updated_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    return user


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(user.id)}"}


def test_parent_can_create_list_update_and_switch_child(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    parent = make_user()
    fake_session.users.append(parent)

    create_response = client.post(
        "/api/family/children",
        headers=auth_header(parent),
        json={"name": "  Mehmet   Yılmaz ", "age": 11, "finance_level": "child"},
    )

    assert create_response.status_code == 201
    child_body = create_response.json()
    assert child_body["name"] == "Mehmet Yılmaz"
    assert child_body["role"] == "child"
    created_child = fake_session.users[1]
    assert created_child.password_hash is None
    assert created_child.parent_id == parent.id

    list_response = client.get("/api/family", headers=auth_header(parent))
    assert list_response.status_code == 200
    assert [member["role"] for member in list_response.json()] == ["parent", "child"]

    patch_response = client.patch(
        f"/api/family/children/{created_child.id}",
        headers=auth_header(parent),
        json={"age": 12},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["age"] == 12

    switch_response = client.post(
        f"/api/family/switch/{created_child.id}",
        headers=auth_header(parent),
    )
    assert switch_response.status_code == 200
    body = switch_response.json()
    assert body["user"]["id"] == str(created_child.id)
    assert body["user"]["role"] == "child"
    assert verify_token(body["access_token"])["sub"] == str(created_child.id)


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
        json={"name": "Yeni Profil", "age": 10, "finance_level": "child"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Aile yönetimi için ebeveyn hesabı gerekli."
