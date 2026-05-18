"""Authenticated speech-to-text endpoint for microphone recordings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth import get_current_user
from app.models.user import User
from app.schemas.stt import SttResponse
from app.services.stt import SttService, SttUnavailableError

router = APIRouter(prefix="/api/stt", tags=["stt"])
MAX_AUDIO_BYTES = 8 * 1024 * 1024


@router.post("", response_model=SttResponse)
async def transcribe_speech(
    audio: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
) -> SttResponse:
    """Transcribe one short microphone turn into text."""
    content = await audio.read()
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Ses kaydı en fazla 8 MB olmalı.",
        )
    try:
        transcript = SttService().transcribe(
            content=content,
            content_type=audio.content_type or "application/octet-stream",
        )
    except SttUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return SttResponse(text=transcript.text)
