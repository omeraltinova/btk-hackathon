"""Authenticated text-to-speech endpoint for written assistant replies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import get_current_user
from app.models.user import User
from app.schemas.tts import TtsRequest
from app.services.tts import TtsService, TtsUnavailableError

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.post("")
def synthesize_tts(
    payload: TtsRequest,
    _current_user: User = Depends(get_current_user),
) -> Response:
    """Return a browser-playable WAV for the requested assistant text."""
    try:
        audio = TtsService().synthesize(payload.text)
    except TtsUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return Response(
        content=audio.content,
        media_type=audio.content_type,
        headers={"Cache-Control": "no-store"},
    )
