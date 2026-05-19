"""Tests for provider-backed microphone speech-to-text."""

from __future__ import annotations

import base64
import subprocess

from pytest import MonkeyPatch, raises

from app.config import Settings
from app.services import stt
from app.services.stt import SttService, SttUnavailableError


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, object]:
        return self._payload


def test_openrouter_stt_uses_chirp_3_for_browser_audio(monkeypatch: MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, str], dict[str, object]]] = []
    content = b"browser-audio"

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        assert timeout == 90.0
        calls.append((url, headers, json))
        return FakeResponse(payload={"text": "Merhaba dünya"})

    monkeypatch.setattr(stt.httpx, "post", fake_post)
    service = SttService(
        Settings(
            app_env="test",
            jwt_secret="test-secret-test-secret-test-secret",
            llm_provider="openrouter",
            openrouter_api_key="router-key",
        ),
    )

    transcript = service.transcribe(content=content, content_type="audio/webm;codecs=opus")

    assert transcript.text == "Merhaba dünya"
    url, headers, body = calls[0]
    assert url.endswith("/audio/transcriptions")
    assert headers["Authorization"] == "Bearer router-key"
    assert body == {
        "model": "google/chirp-3",
        "input_audio": {
            "data": base64.b64encode(content).decode("ascii"),
            "format": "webm",
        },
        "language": "tr",
    }


def test_gemini_stt_uses_multimodal_audio_understanding(monkeypatch: MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, str], dict[str, object]]] = []
    content = b"ogg-audio"

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
                            "parts": [{"text": "Kısa bir transkript"}],
                        },
                    },
                ],
            },
        )

    monkeypatch.setattr(stt.httpx, "post", fake_post)
    service = SttService(
        Settings(
            app_env="test",
            jwt_secret="test-secret-test-secret-test-secret",
            llm_provider="gemini",
            gemini_api_key="gemini-key",
            gemini_model="gemini-2.5-flash",
        ),
    )

    transcript = service.transcribe(content=content, content_type="audio/ogg")

    assert transcript.text == "Kısa bir transkript"
    url, headers, body = calls[0]
    assert url.endswith("/gemini-2.5-flash:generateContent")
    assert headers["x-goog-api-key"] == "gemini-key"
    contents = body["contents"]
    assert isinstance(contents, list)
    parts = contents[0]["parts"]
    assert parts[0] == {
        "inlineData": {
            "mimeType": "audio/ogg",
            "data": base64.b64encode(content).decode("ascii"),
        },
    }
    assert "Transcribe the spoken words" in parts[1]["text"]


def test_gemini_stt_transcodes_unsupported_browser_container(monkeypatch: MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, str], dict[str, object]]] = []
    transcode_calls: list[list[str]] = []
    original_content = b"webm-audio"
    converted_content = b"wav-audio"

    def fake_run(
        command: list[str],
        *,
        input: bytes,
        capture_output: bool,
        check: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[bytes]:
        assert input == original_content
        assert capture_output is True
        assert check is False
        assert timeout == 30.0
        transcode_calls.append(command)
        return subprocess.CompletedProcess(
            command, returncode=0, stdout=converted_content, stderr=b""
        )

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
                            "parts": [{"text": "Dönüştürülmüş kayıt"}],
                        },
                    },
                ],
            },
        )

    monkeypatch.setattr(stt.subprocess, "run", fake_run)
    monkeypatch.setattr(stt.httpx, "post", fake_post)
    service = SttService(
        Settings(
            app_env="test",
            jwt_secret="test-secret-test-secret-test-secret",
            llm_provider="gemini",
            gemini_api_key="gemini-key",
        ),
    )

    transcript = service.transcribe(content=original_content, content_type="audio/webm")

    assert transcript.text == "Dönüştürülmüş kayıt"
    assert transcode_calls[0][0] == "ffmpeg"
    body = calls[0][2]
    contents = body["contents"]
    assert isinstance(contents, list)
    parts = contents[0]["parts"]
    assert parts[0] == {
        "inlineData": {
            "mimeType": "audio/wav",
            "data": base64.b64encode(converted_content).decode("ascii"),
        },
    }


def test_gemini_stt_surfaces_failed_transcode(monkeypatch: MonkeyPatch) -> None:
    def fake_run(
        command: list[str],
        *,
        input: bytes,
        capture_output: bool,
        check: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, returncode=1, stdout=b"", stderr=b"broken")

    monkeypatch.setattr(stt.subprocess, "run", fake_run)
    service = SttService(
        Settings(
            app_env="test",
            jwt_secret="test-secret-test-secret-test-secret",
            llm_provider="gemini",
            gemini_api_key="gemini-key",
        ),
    )

    with raises(SttUnavailableError, match="Bu ses biçimi şu an işlenemedi."):
        service.transcribe(content=b"webm-audio", content_type="audio/webm")
