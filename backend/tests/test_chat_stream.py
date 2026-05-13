from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.auth import create_token
from app.db import get_db
from app.main import app
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.message import Message
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
    def __init__(self, user: User, categories: list[Category], transactions: list[Transaction]):
        self.users = [user]
        self.categories = categories
        self.transactions = transactions
        self.conversations: list[Conversation] = []
        self.messages: list[Message] = []

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is User:
            user_id = self._lookup(statement, "id")
            return FakeResult([user for user in self.users if user.id == user_id])
        if entity is Conversation:
            conversation_id = self._lookup(statement, "id")
            return FakeResult(
                [
                    conversation
                    for conversation in self.conversations
                    if conversation.id == conversation_id
                ],
            )
        if entity is Category:
            return FakeResult(self.categories)
        if entity is Transaction:
            return FakeResult(
                [
                    transaction
                    for transaction in self.transactions
                    if self._matches_transaction(statement, transaction)
                ],
            )
        return FakeResult([])

    def add(self, item: object) -> None:
        if isinstance(item, Conversation):
            if item.id is None:
                item.id = uuid4()
            self.conversations.append(item)
        if isinstance(item, Message):
            if item.id is None:
                item.id = uuid4()
            self.messages.append(item)

    def commit(self) -> None:
        return None

    def refresh(self, item: object) -> None:
        if isinstance(item, Conversation) and item.id is None:
            item.id = uuid4()

    @staticmethod
    def _lookup(statement: object, column_name: str) -> object:
        for criterion in getattr(statement, "_where_criteria", ()):
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            if getattr(left, "name", None) == column_name:
                return getattr(right, "value", None)
        return None

    def _matches_transaction(self, statement: object, transaction: Transaction) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "user_id" and not self._matches_user_id(value, transaction.user_id):
                return False
            if column_name == "type" and transaction.type != value:
                return False
            if column_name == "occurred_at" and transaction.occurred_at < value:
                return False
        return True

    @staticmethod
    def _matches_user_id(value: object, user_id: UUID) -> bool:
        if isinstance(value, list | tuple | set):
            return user_id in value
        return user_id == value


def make_user() -> User:
    user = User(
        id=uuid4(),
        email="ayse@example.com",
        name="Ayşe Yılmaz",
        role="parent",
        parent_id=None,
        password_hash="hash",
        birth_date=date(1988, 1, 1),
        finance_level="beginner",
        is_demo=False,
    )
    user.children = []
    return user


def test_chat_stream_returns_sse_tool_trace_from_scoped_data() -> None:
    user = make_user()
    category = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("125.00"),
        type="expense",
        category_id=category.id,
        description="Alışveriş",
        merchant="Market",
        occurred_at=datetime.now(UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )
    fake_session = FakeSession(user, [category], [transaction])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Bu ay markete ne kadar harcadım?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: tool_call" in response.text
    assert '"tool_name": "get_spending"' in response.text
    assert "125,00 ₺" in response.text
    assert [message.role for message in fake_session.messages] == ["user", "tool", "assistant"]


def test_chat_stream_can_analyze_receipt_attachment_without_persisting_raw_text() -> None:
    user = make_user()
    market = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    receipt_text = """MIGROS TICARET A.S.
TARIH: 12.05.2026 14:32
EKMEK            15,00
SUT              42,50
MEYVE            90,00
TEMIZLIK         100,00
GENEL TOPLAM     247,50 TL
"""
    fake_session = FakeSession(user, [market], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={
                "message": "Bu fişi analiz eder misin?",
                "receipt_image_base64": base64.b64encode(receipt_text.encode()).decode("ascii"),
                "receipt_filename": "migros_demo.txt",
                "receipt_content_type": "text/plain",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "analyze_receipt"' in response.text
    assert "MIGROS TICARET A.S." in response.text
    assert "247,50" in response.text
    assert "₺" in response.text
    assert "raw_text" not in response.text
    assert "receipt_image_base64" not in response.text
    assert [message.role for message in fake_session.messages] == ["user", "tool", "assistant"]
