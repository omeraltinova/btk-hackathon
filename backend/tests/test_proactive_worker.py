from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from pytest import MonkeyPatch

from app.models.user import User
from app.workers import proactive


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
    def __init__(self, users: list[User]) -> None:
        self.users = users

    def execute(self, statement: object) -> FakeResult:
        return FakeResult([user for user in self.users if user.role != "child"])


def make_user(role: str) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        name="Test Kullanıcı",
        role=role,
        parent_id=None,
        password_hash="hash",
        birth_date=date(1991, 1, 1),
        finance_level="beginner",
        is_demo=False,
    )
    user.children = []
    return user


def test_refresh_all_insights_skips_child_profiles(monkeypatch: MonkeyPatch) -> None:
    parent = make_user("parent")
    individual = make_user("individual")
    child = make_user("child")
    db = FakeSession([parent, individual, child])
    refreshed_ids: list[str] = []

    def fake_refresh(db_session: FakeSession, user: User) -> list[object]:
        assert db_session is db
        refreshed_ids.append(str(user.id))
        return []

    monkeypatch.setattr(proactive, "refresh_insights_for_user", fake_refresh)

    count = proactive.refresh_all_insights(db)  # type: ignore[arg-type]

    assert count == 2
    assert refreshed_ids == [str(parent.id), str(individual.id)]
