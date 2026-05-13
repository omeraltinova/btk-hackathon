from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.routers.conversations import delete_conversation, get_conversation_messages


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
        self.conversations: list[Conversation] = []
        self.messages: list[Message] = []
        self.committed = False

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is Conversation:
            return FakeResult(
                [
                    conversation
                    for conversation in self.conversations
                    if self._matches_conversation(statement, conversation)
                ],
            )
        if entity is Message:
            return FakeResult(
                [message for message in self.messages if self._matches_message(statement, message)],
            )
        return FakeResult([])

    def delete(self, conversation: Conversation) -> None:
        self.conversations.remove(conversation)

    def commit(self) -> None:
        self.committed = True

    @staticmethod
    def _matches_conversation(statement: object, conversation: Conversation) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "id" and conversation.id != value:
                return False
            if column_name == "user_id" and conversation.user_id != value:
                return False
        return True

    @staticmethod
    def _matches_message(statement: object, message: Message) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "conversation_id" and message.conversation_id != value:
                return False
        return True


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


def make_conversation(user: User) -> Conversation:
    return Conversation(
        id=uuid4(),
        user_id=user.id,
        started_at=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )


def make_message(conversation: Conversation, *, role: str, content: str) -> Message:
    return Message(
        id=uuid4(),
        conversation_id=conversation.id,
        role=role,
        content=content,
        created_at=datetime(2026, 5, 13, 10, 5, tzinfo=UTC),
    )


def test_conversation_messages_include_historical_chart_and_image_attachments() -> None:
    user = make_user()
    conversation = make_conversation(user)
    chart_message = make_message(conversation, role="tool", content="Grafik hazır.")
    chart_message.tool_name = "visualize_spending"
    chart_message.tool_calls = {
        "result": {
            "chart": {
                "type": "bar",
                "title": "Market harcaması",
                "data": [{"label": "Market", "value": "125.00", "value_formatted": "125,00 ₺"}],
            },
        },
    }
    image_message = make_message(conversation, role="tool", content="Görsel hazır.")
    image_message.tool_name = "illustrate_concept"
    image_message.tool_calls = {
        "result": {
            "image_url": "http://localhost:9000/illustrations/demo/faiz.png",
            "alt_text": "Faiz kavramını anlatan görsel",
        },
    }
    fake_session = FakeSession()
    fake_session.conversations.append(conversation)
    fake_session.messages.extend(
        [
            make_message(conversation, role="user", content="Grafik çiz."),
            chart_message,
            image_message,
        ],
    )

    result = get_conversation_messages(conversation.id, fake_session, user, limit=200)

    tool_messages = [message for message in result.messages if message.role == "tool"]
    assert tool_messages[0].attachments[0].type == "chart"
    assert tool_messages[0].attachments[0].chart is not None
    assert tool_messages[0].attachments[0].chart["data"][0]["value"] == "125.00"
    assert tool_messages[1].attachments[0].type == "image"
    assert tool_messages[1].attachments[0].image_url == (
        "http://localhost:9000/illustrations/demo/faiz.png"
    )


def test_delete_conversation_is_scoped_to_current_user() -> None:
    user = make_user()
    other = make_user()
    conversation = make_conversation(user)
    other_conversation = make_conversation(other)
    fake_session = FakeSession()
    fake_session.conversations.extend([conversation, other_conversation])

    response = delete_conversation(conversation.id, fake_session, user)

    assert response.status_code == 204
    assert fake_session.conversations == [other_conversation]
    assert fake_session.committed is True

    with pytest.raises(HTTPException) as exc_info:
        delete_conversation(other_conversation.id, fake_session, user)
    assert exc_info.value.status_code == 404
