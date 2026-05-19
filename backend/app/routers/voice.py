"""Authenticated voice-chat bootstrap endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import get_current_user
from app.models.user import User
from app.schemas.voice import VoiceSessionResponse
from app.services.voice import VoiceSessionService, VoiceSessionUnavailableError

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/session", response_model=VoiceSessionResponse)
def create_voice_session(
    response: Response,
    _current_user: User = Depends(get_current_user),
) -> VoiceSessionResponse:
    """Return the selected provider's safe client bootstrap for voice chat."""
    try:
        session = VoiceSessionService().create_session()
    except VoiceSessionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return VoiceSessionResponse(
        provider=session.provider,
        mode=session.mode,
        model=session.model,
        voice_name=session.voice_name,
        ephemeral_token=session.ephemeral_token,
        expires_at=session.expires_at,
    )
