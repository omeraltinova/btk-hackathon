"""Tests for provider-backed assistant text-to-speech."""

from __future__ import annotations

import base64

from fastapi import HTTPException
from pytest import MonkeyPatch, raises

from app.config import Settings
from app.routers.tts import synthesize_tts
from app.schemas.tts import TtsRequest
from app.services import tts
from app.services.tts import TtsAudio, TtsService, TtsUnavailableError


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: dict[str, object] | None = None,
        content: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content

    def json(self) -> dict[str, object]:
        return self._payload


def test_speech_text_strips_lightweight_markdown() -> None:
    text = TtsService._speech_text(
        """
        ## Başlık

        - **Birinci** madde
        2. [İkinci](https://example.com) madde

        ![görsel](https://example.com/image.png)
        """,
    )

    assert text == "Başlık\nBirinci madde\nİkinci madde"


def test_gemini_tts_uses_31_model_and_returns_wav(monkeypatch: MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, str], dict[str, object]]] = []
    pcm = b"\x01\x00\x02\x00"

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        assert timeout == 90.0
        calls.append((url, headers, json))
        return FakeResponse(
            payload={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"inlineData": {"data": base64.b64encode(pcm).decode("ascii")}},
                            ],
                        },
                    },
                ],
            },
        )

    monkeypatch.setattr(tts.httpx, "post", fake_post)
    service = TtsService(
        Settings(
            app_env="test",
            jwt_secret="test-secret-test-secret-test-secret",
            llm_provider="gemini",
            gemini_api_key="gemini-key",
        ),
    )

    audio = service.synthesize("Merhaba")

    assert audio.content.startswith(b"RIFF")
    assert b"WAVE" in audio.content[:16]
    url, headers, body = calls[0]
    assert url.endswith("/gemini-3.1-flash-tts-preview:generateContent")
    assert headers["x-goog-api-key"] == "gemini-key"
    generation_config = body["generationConfig"]
    assert isinstance(generation_config, dict)
    assert generation_config["responseModalities"] == ["AUDIO"]
    speech_config = generation_config["speechConfig"]
    assert isinstance(speech_config, dict)
    voice_config = speech_config["voiceConfig"]
    assert isinstance(voice_config, dict)
    prebuilt = voice_config["prebuiltVoiceConfig"]
    assert isinstance(prebuilt, dict)
    assert prebuilt["voiceName"] == "Kore"


def test_openrouter_tts_uses_google_31_model(monkeypatch: MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        assert timeout == 90.0
        calls.append((url, headers, json))
        return FakeResponse(content=b"\x01\x00\x02\x00")

    monkeypatch.setattr(tts.httpx, "post", fake_post)
    service = TtsService(
        Settings(
            app_env="test",
            jwt_secret="test-secret-test-secret-test-secret",
            llm_provider="openrouter",
            openrouter_api_key="router-key",
        ),
    )

    audio = service.synthesize("Merhaba")

    assert audio.content.startswith(b"RIFF")
    url, headers, body = calls[0]
    assert url.endswith("/audio/speech")
    assert headers["Authorization"] == "Bearer router-key"
    assert body == {
        "model": "google/gemini-3.1-flash-tts-preview",
        "input": "Merhaba",
        "voice": "Kore",
        "response_format": "pcm",
    }


def test_tts_router_surfaces_provider_failures(monkeypatch: MonkeyPatch) -> None:
    def fake_synthesize(self: TtsService, text: str) -> TtsAudio:
        raise TtsUnavailableError("Sesli okuma servisi şu an hazır değil.")

    monkeypatch.setattr(TtsService, "synthesize", fake_synthesize)

    with raises(HTTPException) as exc_info:
        synthesize_tts(TtsRequest(text="Merhaba"), _current_user=object())  # type: ignore[arg-type]

    assert getattr(exc_info.value, "status_code", None) == 503
    assert getattr(exc_info.value, "detail", None) == "Sesli okuma servisi şu an hazır değil."
