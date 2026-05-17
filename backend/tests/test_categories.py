from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.models.category import Category
from app.models.user import User
from app.routers.categories import (
    create_category,
    create_envelope_budget,
    delete_envelope_budget,
    list_categories,
    update_envelope_budget,
)
from app.schemas.category import CategoryBudgetUpdate, CategoryCreate, EnvelopeCreate


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
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "id":
                return FakeResult(
                    [category for category in self.categories if category.id == value]
                )
        if "lower(categories.name)" in text:
            requested_name = None
            for criterion in getattr(statement, "_where_criteria", ()):
                left_text = str(getattr(criterion, "left", "")).lower()
                value = getattr(getattr(criterion, "right", None), "value", None)
                if "lower" in left_text and isinstance(value, str):
                    requested_name = value.lower()
            return FakeResult(
                [
                    category
                    for category in self.categories
                    if category.user_id == self.user_ids[0]
                    and (requested_name is None or category.name.lower() == requested_name)
                ],
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

    def delete(self, category: Category) -> None:
        self.categories = [item for item in self.categories if item is not category]


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


def test_update_envelope_budget_creates_user_shadow_for_system_category() -> None:
    user = make_user()
    system_market = make_category("Market")
    db = FakeSession([system_market], user_ids=[user.id])

    result = update_envelope_budget(
        "market",
        CategoryBudgetUpdate(budget_monthly=Decimal("3200.00")),
        db=db,
        current_user=user,
    )

    assert result.user_id == user.id
    assert result.name == "Market"
    assert result.budget_monthly == Decimal("3200.00")
    assert system_market.budget_monthly is None
    assert db.committed is True


def test_update_envelope_budget_updates_existing_user_category() -> None:
    user = make_user()
    user_bill = make_category("Fatura", user.id)
    user_bill.budget_monthly = Decimal("900.00")
    db = FakeSession([make_category("Fatura"), user_bill], user_ids=[user.id])

    result = update_envelope_budget(
        "fatura",
        CategoryBudgetUpdate(budget_monthly=Decimal("1200.00")),
        db=db,
        current_user=user,
    )

    assert result is user_bill
    assert user_bill.budget_monthly == Decimal("1200.00")
    assert db.committed is True


def test_update_envelope_budget_accepts_zero_to_disable_user_zarf() -> None:
    user = make_user()
    user_transport = make_category("Ulaşım", user.id)
    user_transport.budget_monthly = Decimal("750.00")
    db = FakeSession([make_category("Ulaşım"), user_transport], user_ids=[user.id])

    result = update_envelope_budget(
        "ulasim",
        CategoryBudgetUpdate(budget_monthly=Decimal("0.00")),
        db=db,
        current_user=user,
    )

    assert result is user_transport
    assert user_transport.budget_monthly == Decimal("0.00")
    assert db.committed is True


def test_delete_envelope_budget_removes_user_shadow_without_mutating_system_default() -> None:
    user = make_user()
    system_school = make_category("Eğitim")
    system_school.budget_monthly = Decimal("1500.00")
    user_school = make_category("Eğitim", user.id)
    user_school.budget_monthly = Decimal("900.00")
    db = FakeSession([system_school, user_school], user_ids=[user.id])

    response = delete_envelope_budget("okul", db=db, current_user=user)

    assert response.status_code == 204
    assert user_school not in db.categories
    assert system_school.budget_monthly == Decimal("1500.00")
    assert db.committed is True


def test_create_envelope_budget_creates_custom_category_zarf() -> None:
    user = make_user()
    db = FakeSession(user_ids=[user.id])

    result = create_envelope_budget(
        EnvelopeCreate(name="Evcil hayvan", budget_monthly=Decimal("850.00")),
        db=db,
        current_user=user,
    )

    assert result.user_id == user.id
    assert result.name == "Evcil hayvan"
    assert result.budget_monthly == Decimal("850.00")
    assert db.committed is True


def test_delete_custom_envelope_budget_removes_owner_category() -> None:
    user = make_user()
    custom = make_category("Evcil hayvan", user.id)
    custom.budget_monthly = Decimal("850.00")
    db = FakeSession([custom], user_ids=[user.id])

    response = delete_envelope_budget(f"custom-{custom.id}", db=db, current_user=user)

    assert response.status_code == 204
    assert custom not in db.categories
    assert db.committed is True


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
