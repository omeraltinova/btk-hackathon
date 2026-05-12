"""Small streaming runner that turns scoped tool results into SSE events."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TypedDict
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools import (
    build_spending_summary,
    build_subscriptions_summary,
    infer_category_from_text,
)
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.schemas.chat import ChatStreamRequest


class ChatStreamEvent(TypedDict, total=False):
    type: str
    conversation_id: str
    role: str
    content: str
    tool_name: str
    input: dict[str, object]
    result: dict[str, object]


SUBSCRIPTION_HINTS = ("abonelik", "abonelikler", "tekrarlayan", "subscription")


def _get_or_create_conversation(
    db: Session,
    current_user: User,
    conversation_id: UUID | None,
) -> Conversation:
    if conversation_id is None:
        conversation = Conversation(user_id=current_user.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    existing = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id.in_(visible_user_ids(current_user)),
        ),
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sohbet bulunamadı.",
        )
    return existing


def _persist_message(
    db: Session,
    conversation: Conversation,
    *,
    role: str,
    content: str,
    tool_name: str | None = None,
    tool_calls: dict[str, object] | None = None,
) -> None:
    db.add(
        Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_calls=tool_calls,
        ),
    )
    db.commit()


def _chunks(text: str) -> Iterator[str]:
    words = text.split(" ")
    bucket: list[str] = []
    for word in words:
        bucket.append(word)
        if len(bucket) == 7:
            yield " ".join(bucket) + " "
            bucket = []
    if bucket:
        yield " ".join(bucket)


def _wants_subscriptions(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in SUBSCRIPTION_HINTS)


def _int_result(result: dict[str, object], key: str) -> int:
    value = result[key]
    if isinstance(value, int):
        return value
    return int(str(value))


def _spending_answer(result: dict[str, object]) -> str:
    category = result.get("category")
    category_text = f"{category} kategorisinde" if category else "tüm kategorilerde"
    total = str(result["total_amount_formatted"])
    count = _int_result(result, "transaction_count")
    days = _int_result(result, "days")
    if count == 0:
        return (
            f"Son {days} günde {category_text} kayıtlı gider bulamadım. "
            "İlk işlemini eklediğinde buradan gerçek veriye göre yanıt verebilirim."
        )
    return (
        f"Son {days} günde {category_text} toplam harcaman {total}. "
        f"Bu tutar {count} işlemden hesaplandı."
    )


def _subscription_answer(result: dict[str, object]) -> str:
    count = _int_result(result, "count")
    total = str(result["monthly_total_formatted"])
    if count == 0:
        return (
            "Aktif abonelik veya tekrarlayan ödeme kaydı bulamadım. "
            "Eklediğinde aylık etkisini burada birlikte takip edebiliriz."
        )
    return f"Aktif tekrarlayan ödemelerin aylık etkisi {total}. Toplam {count} kayıt var."


def stream_chat_turn(
    db: Session,
    current_user: User,
    payload: ChatStreamRequest,
) -> Iterator[ChatStreamEvent]:
    """Yield a deterministic Day 3 SSE stream from real scoped tool calls."""
    conversation = _get_or_create_conversation(db, current_user, payload.conversation_id)
    conversation_id = str(conversation.id)
    yield {"type": "message_start", "conversation_id": conversation_id, "role": "assistant"}
    _persist_message(db, conversation, role="user", content=payload.message)

    if _wants_subscriptions(payload.message):
        tool_input: dict[str, object] = {"only_active": True}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "get_subscriptions",
            "input": tool_input,
        }
        result = build_subscriptions_summary(db, current_user, only_active=True)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Abonelik özeti alındı.",
            tool_name="get_subscriptions",
            tool_calls={"input": tool_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "get_subscriptions",
            "result": result,
        }
        answer = _subscription_answer(result)
    else:
        category = infer_category_from_text(db, current_user, payload.message)
        tool_input = {"category": category, "days": 30}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "get_spending",
            "input": tool_input,
        }
        result = build_spending_summary(db, current_user, category=category, days=30)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Harcama özeti alındı.",
            tool_name="get_spending",
            tool_calls={"input": tool_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "get_spending",
            "result": result,
        }
        answer = _spending_answer(result)

    for chunk in _chunks(answer):
        yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}

    _persist_message(db, conversation, role="assistant", content=answer)
    yield {"type": "done", "conversation_id": conversation_id}
