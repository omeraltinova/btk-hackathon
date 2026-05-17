from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.models.category import Category
from app.models.subscription import Subscription
from app.models.user import User
from app.routers.subscriptions import (
    create_subscription,
    delete_subscription,
    list_subscriptions,
    update_subscription,
)
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate


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
        self,
        subscriptions: list[Subscription] | None = None,
        categories: list[Category] | None = None,
        user_ids: list[UUID] | None = None,
    ) -> None:
        self.subscriptions = subscriptions or []
        self.categories = categories or []
        self.user_ids = user_ids or []
        self.committed = False

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is Subscription:
            items = [
                subscription
                for subscription in self.subscriptions
                if self._matches_subscription(statement, subscription)
            ]
            return FakeResult(items)
        if entity is Category:
            items = [
                category
                for category in self.categories
                if self._matches_category(statement, category)
            ]
            return FakeResult(items)
        return FakeResult([])

    def add(self, subscription: Subscription) -> None:
        if subscription.id is None:
            subscription.id = uuid4()
        self.subscriptions.append(subscription)

    def commit(self) -> None:
        self.committed = True

    def refresh(self, subscription: Subscription) -> None:
        if subscription.id is None:
            subscription.id = uuid4()

    def delete(self, subscription: Subscription) -> None:
        self.subscriptions.remove(subscription)

    def _matches_subscription(self, statement: object, subscription: Subscription) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "id" and subscription.id != value:
                return False
            if column_name == "user_id" and not self._matches_user_id(value, subscription.user_id):
                return False
        return True

    def _matches_category(self, statement: object, category: Category) -> bool:
        requested_id = None
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "id":
                requested_id = value
        return category.id == requested_id and (
            category.user_id is None or category.user_id in self.user_ids
        )

    @staticmethod
    def _matches_user_id(value: object, user_id: UUID) -> bool:
        if isinstance(value, list | tuple | set):
            return user_id in value
        return user_id == value


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


def make_subscription(
    user_id: UUID, amount: str = "100.00", cycle: str = "monthly"
) -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user_id,
        name="Tekrarlayan ödeme",
        merchant="Hizmet",
        amount=Decimal(amount),
        type="expense",
        billing_cycle=cycle,
        recurrence_interval=1,
        recurrence_unit={"weekly": "week", "yearly": "year"}.get(cycle, "month"),
        next_billing_date=date(2026, 6, 1),
        category_id=None,
        is_active=True,
        detected_from_transactions=False,
        usage_score=None,
    )


def make_category(user_id: UUID | None = None) -> Category:
    return Category(
        id=uuid4(),
        user_id=user_id,
        name="Fatura",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )


def test_list_subscriptions_filters_to_current_user_and_calculates_monthly_equivalent() -> None:
    user = make_user()
    other_user = make_user()
    own = make_subscription(user.id, "75.00", "weekly")
    other = make_subscription(other_user.id, "200.00")
    db = FakeSession([own, other], user_ids=[user.id])

    result = list_subscriptions(db=db, current_user=user)

    assert len(result) == 1
    assert result[0].id == own.id
    assert result[0].monthly_equivalent == Decimal("300.00")


def test_create_subscription_assigns_current_user_and_validates_category() -> None:
    user = make_user()
    category = make_category()
    db = FakeSession(categories=[category], user_ids=[user.id])

    result = create_subscription(
        SubscriptionCreate(
            name="  Elektrik faturası  ",
            merchant="  Dağıtım şirketi  ",
            amount=Decimal("450.25"),
            billing_cycle="monthly",
            next_billing_date=date(2026, 6, 10),
            category_id=category.id,
        ),
        db=db,
        current_user=user,
    )

    assert result.user_id == user.id
    assert result.name == "Elektrik faturası"
    assert result.merchant == "Dağıtım şirketi"
    assert result.type == "expense"
    assert result.category_id == category.id
    assert result.monthly_equivalent == Decimal("450.25")
    assert db.committed is True


def test_create_subscription_accepts_recurring_income() -> None:
    user = make_user()
    category = make_category()
    category.name = "Maaş"
    db = FakeSession(categories=[category], user_ids=[user.id])

    result = create_subscription(
        SubscriptionCreate(
            name="Maaş",
            merchant="Okul",
            amount=Decimal("32000.00"),
            type="income",
            billing_cycle="monthly",
            next_billing_date=date(2026, 6, 1),
            category_id=category.id,
        ),
        db=db,
        current_user=user,
    )

    assert result.type == "income"
    assert result.amount == Decimal("32000.00")
    assert result.monthly_equivalent == Decimal("32000.00")
    assert db.subscriptions[0].type == "income"
    assert db.committed is True


def test_create_custom_subscription_stores_interval_and_monthly_equivalent() -> None:
    user = make_user()
    db = FakeSession(user_ids=[user.id])

    result = create_subscription(
        SubscriptionCreate(
            name="Üç ayda bir yurt",
            merchant="Yurt",
            amount=Decimal("6000.00"),
            billing_cycle="custom",
            recurrence_interval=3,
            recurrence_unit="month",
        ),
        db=db,
        current_user=user,
    )

    assert result.billing_cycle == "custom"
    assert result.recurrence_interval == 3
    assert result.recurrence_unit == "month"
    assert result.recurrence_label == "Her 3 ayda bir"
    assert result.monthly_equivalent == Decimal("2000.00")


def test_update_subscription_rejects_other_user_row() -> None:
    user = make_user()
    other_user = make_user()
    other = make_subscription(other_user.id)
    db = FakeSession([other], user_ids=[user.id])

    with pytest.raises(HTTPException) as exc:
        update_subscription(other.id, SubscriptionUpdate(is_active=False), db=db, current_user=user)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Tekrarlayan kayıt bulunamadı."


def test_delete_subscription_removes_scoped_row() -> None:
    user = make_user()
    subscription = make_subscription(user.id)
    db = FakeSession([subscription], user_ids=[user.id])

    response = delete_subscription(subscription.id, db=db, current_user=user)

    assert response.status_code == 204
    assert db.subscriptions == []
    assert db.committed is True
