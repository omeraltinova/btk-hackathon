from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class VoiceSessionResponse(BaseModel):
    provider: Literal["gemini", "openrouter"]
    mode: Literal["realtime", "cascade"]
    model: str | None = None
    voice_name: str | None = None
    ephemeral_token: str | None = None
    expires_at: datetime | None = None
