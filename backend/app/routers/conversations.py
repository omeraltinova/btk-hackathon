"""Conversation history router.

Read-only endpoints that surface past chat sessions for the *current* user.
Strict per-user scope: a parent who wants to read a child's chat history must
explicitly switch into the child profile (Day 5 family-switch issues a JWT for
the child). This is intentionally stricter than `visible_user_ids` because
chat content is personal narrative, not aggregate family finance data.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.conversation import (
    ConversationListItem,
    ConversationMessage,
    ConversationMessages,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

MAX_CONVERSATIONS = 100
MAX_MESSAGES = 200


@router.get("", response_model=list[ConversationListItem])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=MAX_CONVERSATIONS),
) -> list[ConversationListItem]:
    last_message_subq = (
        select(
            Message.conversation_id.label("conversation_id"),
            func.max(Message.created_at).label("last_at"),
            func.count(Message.id).label("message_count"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    rows = db.execute(
        select(Conversation, last_message_subq.c.last_at, last_message_subq.c.message_count)
        .join(
            last_message_subq,
            last_message_subq.c.conversation_id == Conversation.id,
            isouter=True,
        )
        .where(Conversation.user_id == current_user.id)
        .order_by(
            desc(func.coalesce(last_message_subq.c.last_at, Conversation.started_at)),
        )
        .limit(limit),
    ).all()

    items: list[ConversationListItem] = []
    for conversation, last_at, message_count in rows:
        preview_row = db.execute(
            select(Message.content)
            .where(
                Message.conversation_id == conversation.id,
                Message.role == "user",
            )
            .order_by(Message.created_at)
            .limit(1),
        ).scalar_one_or_none()
        items.append(
            ConversationListItem(
                id=conversation.id,
                started_at=conversation.started_at,
                last_message_at=last_at,
                message_count=int(message_count or 0),
                preview=(preview_row or None),
            ),
        )
    return items


@router.get("/{conversation_id}/messages", response_model=ConversationMessages)
def get_conversation_messages(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=MAX_MESSAGES),
) -> ConversationMessages:
    conversation = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        ),
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sohbet bulunamadı.",
        )

    rows = list(
        db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
            .limit(limit),
        )
        .scalars()
        .all(),
    )
    messages = [
        ConversationMessage(
            id=row.id,
            role=row.role,
            content=row.content,
            tool_name=row.tool_name,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return ConversationMessages(
        conversation_id=conversation.id,
        started_at=conversation.started_at,
        message_count=len(messages),
        messages=messages,
    )
