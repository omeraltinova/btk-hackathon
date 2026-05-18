"""Provider-backed speech-to-text for microphone recordings."""

from __future__ import annotations

import base64
import json
import logging
import subprocess
import unicodedata
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

OPENROUTER_STT_MODEL_DEFAULT = "google/chirp-3"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_TRANSCODE_TARGET_TYPE = "audio/wav"
GEMINI_SUPPORTED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/aiff",
    "audio/aac",
    "audio/ogg",
    "audio/flac",
}
OPENROUTER_FORMATS = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/flac": "flac",
    "audio/mp4": "m4a",
    "audio/aac": "aac",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
}


class SttUnavailableError(RuntimeError):
    """Raised when provider-backed speech recognition cannot complete."""


@dataclass(frozen=True)
class SttTranscript:
    """Normalized text returned from a voice recording."""

    text: str


class SttService:
    """Transcribe one short microphone recording."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def transcribe(self, *, content: bytes, content_type: str) -> SttTranscript:
        normalized_type = self._normalized_content_type(content_type)
        if not content:
            raise SttUnavailableError("Ses kaydı boş görünüyor.")

        if self._settings.llm_provider == "openrouter":
            if not self._settings.openrouter_api_key:
                raise SttUnavailableError("Sesli yazma servisi şu an hazır değil.")
            text = self._call_openrouter(content=content, content_type=normalized_type)
        else:
            if not self._settings.gemini_api_key:
                raise SttUnavailableError("Sesli yazma servisi şu an hazır değil.")
            text = self._call_gemini(content=content, content_type=normalized_type)

        normalized_text = " ".join(text.split()).strip()
        if not normalized_text:
            raise SttUnavailableError("Ses kaydında anlaşılır konuşma bulunamadı.")
        return SttTranscript(text=normalized_text)

    @staticmethod
    def _normalized_content_type(content_type: str) -> str:
        return content_type.split(";", 1)[0].strip().lower()

    @staticmethod
    def _ascii_header(raw: str | None) -> str | None:
        if raw is None:
            return None
        normalized = unicodedata.normalize("NFKD", raw)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii").strip()
        return ascii_text or None

    def _call_openrouter(self, *, content: bytes, content_type: str) -> str:
        audio_format = OPENROUTER_FORMATS.get(content_type)
        if audio_format is None:
            raise SttUnavailableError("Bu ses biçimi şu an işlenemedi.")
        url = f"{self._settings.openrouter_base_url.rstrip('/')}/audio/transcriptions"
        body: dict[str, object] = {
            "model": self._settings.openrouter_stt_model or OPENROUTER_STT_MODEL_DEFAULT,
            "input_audio": {
                "data": base64.b64encode(content).decode("ascii"),
                "format": audio_format,
            },
            "language": "tr",
        }
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key or ''}",
            "Content-Type": "application/json",
        }
        if self._settings.openrouter_http_referer:
            headers["HTTP-Referer"] = (
                self._ascii_header(self._settings.openrouter_http_referer)
                or "http://localhost:3000"
            )
        if self._settings.openrouter_app_title:
            headers["X-Title"] = (
                self._ascii_header(self._settings.openrouter_app_title) or "Cuzdan Kocu"
            )
        try:
            response = httpx.post(url, headers=headers, json=body, timeout=90.0)
        except httpx.HTTPError as exc:
            logger.warning("stt_openrouter_error: %s", type(exc).__name__)
            raise SttUnavailableError("Sesli yazma servisi şu an cevap vermedi.") from exc

        if response.status_code >= 400:
            logger.warning("stt_openrouter_http_error: status=%s", response.status_code)
            raise SttUnavailableError("Sesli yazma servisi şu an cevap vermedi.")
        try:
            payload: dict[str, object] = response.json()
        except json.JSONDecodeError as exc:
            raise SttUnavailableError("Sesli yazma yanıtı okunamadı.") from exc
        text = payload.get("text")
        if not isinstance(text, str):
            raise SttUnavailableError("Sesli yazma servisi şu an metin üretmedi.")
        return text

    def _call_gemini(self, *, content: bytes, content_type: str) -> str:
        prepared_content, prepared_content_type = self._prepare_gemini_audio(
            content=content,
            content_type=content_type,
        )
        url = f"{GEMINI_BASE_URL}/{self._settings.gemini_model}:generateContent"
        body: dict[str, object] = {
            "contents": [
                {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": prepared_content_type,
                                "data": base64.b64encode(prepared_content).decode("ascii"),
                            },
                        },
                        {
                            "text": (
                                "Transcribe the spoken words in this audio. "
                                "Return only the transcript, preserve the original language, "
                                "and do not add explanations."
                            ),
                        },
                    ],
                },
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._settings.gemini_api_key or "",
        }
        try:
            response = httpx.post(url, headers=headers, json=body, timeout=90.0)
        except httpx.HTTPError as exc:
            logger.warning("stt_gemini_error: %s", type(exc).__name__)
            raise SttUnavailableError("Sesli yazma servisi şu an cevap vermedi.") from exc
        if response.status_code >= 400:
            logger.warning("stt_gemini_http_error: status=%s", response.status_code)
            raise SttUnavailableError("Sesli yazma servisi şu an cevap vermedi.")
        try:
            payload: dict[str, object] = response.json()
        except json.JSONDecodeError as exc:
            raise SttUnavailableError("Sesli yazma yanıtı okunamadı.") from exc
        text = self._extract_gemini_text(payload)
        if text is None:
            raise SttUnavailableError("Sesli yazma servisi şu an metin üretmedi.")
        return text

    def _prepare_gemini_audio(self, *, content: bytes, content_type: str) -> tuple[bytes, str]:
        if content_type in GEMINI_SUPPORTED_AUDIO_TYPES:
            return content, content_type
        try:
            completed = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-c:a",
                    "pcm_s16le",
                    "-f",
                    "wav",
                    "pipe:1",
                ],
                input=content,
                capture_output=True,
                check=False,
                timeout=30.0,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("stt_gemini_transcode_error: %s", type(exc).__name__)
            raise SttUnavailableError("Bu ses biçimi şu an işlenemedi.") from exc
        if completed.returncode != 0 or not completed.stdout:
            logger.warning("stt_gemini_transcode_failed: returncode=%s", completed.returncode)
            raise SttUnavailableError("Bu ses biçimi şu an işlenemedi.")
        return completed.stdout, GEMINI_TRANSCODE_TARGET_TYPE

    @staticmethod
    def _extract_gemini_text(payload: dict[str, object]) -> str | None:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return None
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            text_parts = [
                str(part["text"])
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            if text_parts:
                return "\n".join(text_parts)
        return None
