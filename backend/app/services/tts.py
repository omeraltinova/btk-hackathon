"""Provider-backed text-to-speech for assistant message playback."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import unicodedata
import wave
from dataclasses import dataclass
from io import BytesIO

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

GEMINI_TTS_MODEL_DEFAULT = "gemini-3.1-flash-tts-preview"
OPENROUTER_TTS_MODEL_DEFAULT = "google/gemini-3.1-flash-tts-preview"
DEFAULT_TTS_VOICE = "Kore"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
WAV_SAMPLE_RATE = 24000
WAV_CHANNELS = 1
WAV_SAMPLE_WIDTH = 2


class TtsUnavailableError(RuntimeError):
    """Raised when provider-backed TTS cannot produce audio."""


@dataclass(frozen=True)
class TtsAudio:
    """Browser-playable synthesized speech."""

    content: bytes
    content_type: str = "audio/wav"


class TtsService:
    """Generate WAV audio from a written assistant message."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def synthesize(self, text: str) -> TtsAudio:
        speech_text = self._speech_text(text)
        if not speech_text:
            raise TtsUnavailableError("Seslendirilecek metin boş görünüyor.")

        if self._settings.llm_provider == "openrouter":
            if not self._settings.openrouter_api_key:
                raise TtsUnavailableError("Sesli okuma servisi şu an hazır değil.")
            pcm = self._call_openrouter(speech_text)
        else:
            if not self._settings.gemini_api_key:
                raise TtsUnavailableError("Sesli okuma servisi şu an hazır değil.")
            pcm = self._call_gemini(speech_text)

        return TtsAudio(content=self._pcm_to_wav(pcm))

    @staticmethod
    def _speech_text(content: str) -> str:
        """Strip lightweight Markdown so the provider reads natural prose."""
        text = content
        text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", text)
        text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
        text = re.sub(r"^\s*#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"[*_`>]", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _ascii_header(raw: str | None) -> str | None:
        if raw is None:
            return None
        normalized = unicodedata.normalize("NFKD", raw)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii").strip()
        return ascii_text or None

    def _call_gemini(self, text: str) -> bytes:
        model = self._settings.gemini_tts_model or GEMINI_TTS_MODEL_DEFAULT
        url = f"{GEMINI_BASE_URL}/{model}:generateContent"
        body: dict[str, object] = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": self._settings.gemini_tts_voice or DEFAULT_TTS_VOICE,
                        },
                    },
                },
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._settings.gemini_api_key or "",
        }
        try:
            response = httpx.post(url, headers=headers, json=body, timeout=90.0)
        except httpx.HTTPError as exc:
            logger.warning("tts_gemini_error: %s", type(exc).__name__)
            raise TtsUnavailableError("Sesli okuma servisi şu an cevap vermedi.") from exc

        if response.status_code >= 400:
            logger.warning("tts_gemini_http_error: status=%s", response.status_code)
            raise TtsUnavailableError("Sesli okuma servisi şu an cevap vermedi.")

        try:
            payload: dict[str, object] = response.json()
        except json.JSONDecodeError as exc:
            raise TtsUnavailableError("Sesli okuma yanıtı okunamadı.") from exc

        inline_audio = self._extract_gemini_inline_audio(payload)
        if inline_audio is None:
            raise TtsUnavailableError("Sesli okuma servisi şu an ses üretmedi.")
        return inline_audio

    def _call_openrouter(self, text: str) -> bytes:
        model = self._settings.openrouter_tts_model or OPENROUTER_TTS_MODEL_DEFAULT
        url = f"{self._settings.openrouter_base_url.rstrip('/')}/audio/speech"
        body: dict[str, object] = {
            "model": model,
            "input": text,
            "voice": self._settings.openrouter_tts_voice or DEFAULT_TTS_VOICE,
            "response_format": "pcm",
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
            logger.warning("tts_openrouter_error: %s", type(exc).__name__)
            raise TtsUnavailableError("Sesli okuma servisi şu an cevap vermedi.") from exc

        if response.status_code >= 400:
            logger.warning("tts_openrouter_http_error: status=%s", response.status_code)
            raise TtsUnavailableError("Sesli okuma servisi şu an cevap vermedi.")
        if not response.content:
            raise TtsUnavailableError("Sesli okuma servisi şu an ses üretmedi.")
        return response.content

    @staticmethod
    def _extract_gemini_inline_audio(payload: dict[str, object]) -> bytes | None:
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
            for part in parts:
                if not isinstance(part, dict):
                    continue
                inline = part.get("inline_data") or part.get("inlineData")
                if not isinstance(inline, dict):
                    continue
                data_b64 = inline.get("data")
                if not isinstance(data_b64, str):
                    continue
                try:
                    return base64.b64decode(data_b64, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise TtsUnavailableError("Sesli okuma verisi çözülemedi.") from exc
        return None

    @staticmethod
    def _pcm_to_wav(pcm: bytes) -> bytes:
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(WAV_CHANNELS)
            wav_file.setsampwidth(WAV_SAMPLE_WIDTH)
            wav_file.setframerate(WAV_SAMPLE_RATE)
            wav_file.writeframes(pcm)
        return buffer.getvalue()
