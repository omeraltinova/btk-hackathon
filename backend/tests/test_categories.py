from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.models.category import Category
from app.models.user import User
from app.routers.categories import create_category, list_categories
from app.schemas.category import CategoryCreate


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
    def __init__(
        self, categories: list[Category] | None = None, user_ids: list[UUID] | None = None
    ) -> None:
        self.categories = categories or []
        self.user_ids = user_ids or []
        self.committed = False

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is not Category:
            return FakeResult([])

        text = str(statement)
        if "lower(categories.name)" in text:
            return FakeResult(
                [category for category in self.categories if category.user_id == self.user_ids[0]],
            )

        return FakeResult(
            [
                category
                for category in self.categories
                if category.user_id is None or category.user_id in self.user_ids
            ],
        )

    def add(self, category: Category) -> None:
        if category.id is None:
            category.id = uuid4()
        self.categories.append(category)

    def commit(self) -> None:
        self.committed = True

    def refresh(self, category: Category) -> None:
        if category.id is None:
            category.id = uuid4()


def make_user(*, role: str = "individual") -> User:
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


def make_category(name: str, user_id: UUID | None = None) -> Category:
    return Category(
        id=uuid4(),
        user_id=user_id,
        name=name,
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )


def test_list_categories_returns_defaults_and_user_categories_without_shadowed_default() -> None:
    user = make_user()
    other_user = make_user()
    system_market = make_category("Market")
    custom_market = make_category("Market", user.id)
    system_bill = make_category("Fatura")
    other_custom = make_category("Ev", other_user.id)
    db = FakeSession(
        [system_market, custom_market, system_bill, other_custom],
        user_ids=[user.id],
    )

    result = list_categories(db=db, current_user=user)

    assert result == [system_bill, custom_market]


def test_create_category_assigns_current_user_and_normalizes() -> None:
    user = make_user()
    db = FakeSession(user_ids=[user.id])

    result = create_category(
        CategoryCreate(name="  Ev bütçesi  ", icon="  folder  ", budget_monthly=Decimal("1500.00")),
        db=db,
        current_user=user,
    )

    assert result.user_id == user.id
    assert result.name == "Ev bütçesi"
    assert result.icon == "folder"
    assert result.budget_monthly == Decimal("1500.00")
    assert db.committed is True


def test_create_category_rejects_duplicate_user_category() -> None:
    user = make_user()
    db = FakeSession([make_category("Market", user.id)], user_ids=[user.id])

    with pytest.raises(HTTPException) as exc:
        create_category(CategoryCreate(name="market"), db=db, current_user=user)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Bu kategori zaten var."
