"""Request schemas for provider-backed text-to-speech."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TtsRequest(BaseModel):
    """A single assistant message to synthesize as speech."""

    text: str = Field(min_length=1, max_length=6000)
