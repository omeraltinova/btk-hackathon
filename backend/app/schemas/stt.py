"""Response schemas for provider-backed speech-to-text."""

from __future__ import annotations

from pydantic import BaseModel


class SttResponse(BaseModel):
    """A single transcribed microphone turn."""

    text: str
