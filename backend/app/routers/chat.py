"""Chat router: authenticated SSE stream for the finance coach."""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.chat import ChatStreamRequest
from app.services.agent_runner import ChatStreamEvent, stream_chat_turn

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _encode_sse(event: ChatStreamEvent) -> str:
    event_type = event.get("type", "message")
    data = json.dumps(event, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {data}\n\n"


@router.post("/stream")
def stream_chat(
    payload: ChatStreamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream assistant events; `user_id` comes from the bearer token, not the prompt."""

    def event_generator() -> Iterator[str]:
        for event in stream_chat_turn(db, current_user, payload):
            yield _encode_sse(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
