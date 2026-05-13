from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.models.transaction import Transaction
from app.models.user import User
from app.routers.transactions import (
    create_transaction,
    delete_transaction,
    get_transaction,
    list_transactions,
    update_transaction,
)
from app.schemas.transaction import TransactionCreate, TransactionUpdate


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
    def __init__(self, transactions: list[Transaction] | None = None) -> None:
        self.transactions = transactions or []
        self.committed = False

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is Transaction:
            items = [tx for tx in self.transactions if self._matches_transaction(statement, tx)]
            items.sort(key=lambda tx: tx.occurred_at, reverse=True)
            return FakeResult(items)
        return FakeResult([])

    def add(self, transaction: Transaction) -> None:
        if transaction.id is None:
            transaction.id = uuid4()
        self.transactions.append(transaction)

    def commit(self) -> None:
        self.committed = True

    def refresh(self, transaction: Transaction) -> None:
        if transaction.id is None:
            transaction.id = uuid4()

    def delete(self, transaction: Transaction) -> None:
        self.transactions.remove(transaction)

    def _matches_transaction(self, statement: object, transaction: Transaction) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "id" and transaction.id != value:
                return False
            if column_name == "user_id" and not self._matches_user_id(value, transaction.user_id):
                return False
        return True

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


def make_transaction(user_id: UUID, amount: str = "125.50") -> Transaction:
    return Transaction(
        id=uuid4(),
        user_id=user_id,
        amount=Decimal(amount),
        type="expense",
        category_id=None,
        description="Market alışverişi",
        merchant="Mahalle marketi",
        occurred_at=datetime(2026, 5, 12, 9, 30, tzinfo=UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )


def test_list_transactions_filters_to_current_user() -> None:
    user = make_user()
    other_user = make_user()
    own = make_transaction(user.id, "100.00")
    other = make_transaction(other_user.id, "200.00")
    db = FakeSession([own, other])

    result = list_transactions(db=db, current_user=user)

    assert result == [own]


def test_create_transaction_assigns_current_user() -> None:
    user = make_user()
    db = FakeSession()

    result = create_transaction(
        TransactionCreate(
            amount=Decimal("99.90"),
            type="expense",
            description="  Okul kantini  ",
            merchant=" Kantin ",
            occurred_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        ),
        db=db,
        current_user=user,
    )

    assert result.user_id == user.id
    assert result.amount == Decimal("99.90")
    assert result.description == "Okul kantini"
    assert result.merchant == "Kantin"
    assert result.source == "manual"
    assert db.committed is True


def test_get_transaction_rejects_other_user_row() -> None:
    user = make_user()
    other_user = make_user()
    other = make_transaction(other_user.id)
    db = FakeSession([other])

    with pytest.raises(HTTPException) as exc:
        get_transaction(other.id, db=db, current_user=user)

    assert exc.value.status_code == 404
    assert exc.value.detail == "İşlem bulunamadı."


def test_update_transaction_changes_only_scoped_row() -> None:
    user = make_user()
    transaction = make_transaction(user.id)
    db = FakeSession([transaction])

    result = update_transaction(
        transaction.id,
        TransactionUpdate(amount=Decimal("150.00"), merchant=None),
        db=db,
        current_user=user,
    )

    assert result.amount == Decimal("150.00")
    assert result.merchant is None
    assert db.committed is True


def test_delete_transaction_removes_scoped_row() -> None:
    user = make_user()
    transaction = make_transaction(user.id)
    db = FakeSession([transaction])

    response = delete_transaction(transaction.id, db=db, current_user=user)

    assert response.status_code == 204
    assert db.transactions == []
    assert db.committed is True
