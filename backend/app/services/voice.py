"""Voice-chat session bootstrap for realtime Gemini or cascade fallback mode."""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

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
        client = genai.Client(
            api_key=self._settings.gemini_api_key,
            http_options={"api_version": "v1alpha"},
        )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=genai_errors.ExperimentalWarning)
                auth_token = client.auth_tokens.create(
                    config=genai_types.CreateAuthTokenConfig(
                        uses=1,
                        expire_time=expire_time,
                        new_session_expire_time=new_session_expire_time,
                        http_options=genai_types.HttpOptions(api_version="v1alpha"),
                    ),
                )
        except genai_errors.APIError as exc:
            logger.warning(
                "voice_gemini_token_api_error: code=%s status=%s",
                exc.code,
                exc.status,
            )
            raise VoiceSessionUnavailableError("Canlı sesli sohbet şu an açılamadı.") from exc
        except Exception as exc:
            logger.warning("voice_gemini_token_error: %s", type(exc).__name__)
            raise VoiceSessionUnavailableError("Canlı sesli sohbet şu an açılamadı.") from exc

        token = auth_token.name
        if not isinstance(token, str) or not token:
            raise VoiceSessionUnavailableError("Canlı sesli sohbet token'ı alınamadı.")

        return VoiceSessionTicket(
            provider="gemini",
            mode="realtime",
            model=self._settings.gemini_live_model or DEFAULT_GEMINI_LIVE_MODEL,
            voice_name=self._settings.gemini_live_voice or DEFAULT_GEMINI_LIVE_VOICE,
            ephemeral_token=token,
            expires_at=expire_time,
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
