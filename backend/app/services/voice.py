"""Voice-chat session bootstrap for realtime Gemini or cascade fallback mode."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

GEMINI_AUTH_TOKENS_URL = "https://generativelanguage.googleapis.com/v1alpha/authTokens"
DEFAULT_GEMINI_LIVE_MODEL = "gemini-3.1-flash-live-preview"
DEFAULT_GEMINI_LIVE_VOICE = "Kore"


class VoiceSessionUnavailableError(RuntimeError):
    """Raised when a provider-specific voice session cannot be prepared."""


@dataclass(frozen=True)
class VoiceSessionTicket:
    """Safe-to-return client bootstrap details for one voice-chat session."""

    provider: Literal["gemini", "openrouter"]
    mode: Literal["realtime", "cascade"]
    model: str | None
    voice_name: str | None
    ephemeral_token: str | None
    expires_at: datetime | None


class VoiceSessionService:
    """Create the right voice-chat bootstrap for the selected provider family."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def create_session(self) -> VoiceSessionTicket:
        if self._settings.llm_provider == "openrouter":
            return VoiceSessionTicket(
                provider="openrouter",
                mode="cascade",
                model=None,
                voice_name=None,
                ephemeral_token=None,
                expires_at=None,
            )

        if not self._settings.gemini_api_key:
            raise VoiceSessionUnavailableError("Canlı sesli sohbet şu an hazır değil.")

        now = datetime.now(UTC)
        expire_time = now + timedelta(minutes=30)
        new_session_expire_time = now + timedelta(minutes=1)
        body: dict[str, object] = {
            "authToken": {
                "uses": 1,
                "expireTime": self._format_timestamp(expire_time),
                "newSessionExpireTime": self._format_timestamp(new_session_expire_time),
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._settings.gemini_api_key,
        }
        try:
            response = httpx.post(
                GEMINI_AUTH_TOKENS_URL,
                headers=headers,
                json=body,
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("voice_gemini_token_error: %s", type(exc).__name__)
            raise VoiceSessionUnavailableError("Canlı sesli sohbet şu an açılamadı.") from exc

        if response.status_code >= 400:
            logger.warning("voice_gemini_token_http_error: status=%s", response.status_code)
            raise VoiceSessionUnavailableError("Canlı sesli sohbet şu an açılamadı.")

        try:
            payload: dict[str, object] = response.json()
        except json.JSONDecodeError as exc:
            raise VoiceSessionUnavailableError("Canlı sesli sohbet yanıtı okunamadı.") from exc

        token = payload.get("name")
        if not isinstance(token, str) or not token:
            raise VoiceSessionUnavailableError("Canlı sesli sohbet token'ı alınamadı.")

        payload_expire_time = payload.get("expireTime")
        parsed_expiry = (
            self._parse_timestamp(payload_expire_time)
            if isinstance(payload_expire_time, str)
            else None
        )
        return VoiceSessionTicket(
            provider="gemini",
            mode="realtime",
            model=self._settings.gemini_live_model or DEFAULT_GEMINI_LIVE_MODEL,
            voice_name=self._settings.gemini_live_voice or DEFAULT_GEMINI_LIVE_VOICE,
            ephemeral_token=token,
            expires_at=parsed_expiry or expire_time,
        )

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
