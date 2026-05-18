"""Tests for voice-chat session bootstrap."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, Response
from pytest import MonkeyPatch, raises

from app.config import Settings
from app.routers.voice import create_voice_session
from app.services import voice
from app.services.voice import VoiceSessionService, VoiceSessionUnavailableError


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


def test_openrouter_voice_session_uses_cascade_mode() -> None:
    session = VoiceSessionService(
        Settings(
            app_env="test",
            jwt_secret="test-secret-test-secret-test-secret",
            llm_provider="openrouter",
            openrouter_api_key="router-key",
        ),
    ).create_session()

    assert session.provider == "openrouter"
    assert session.mode == "cascade"
    assert session.model is None
    assert session.ephemeral_token is None


def test_gemini_voice_session_requests_ephemeral_token(monkeypatch: MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        assert timeout == 30.0
        calls.append((url, headers, json))
        return FakeResponse(
            payload={
                "name": "ephemeral-token",
                "expireTime": "2026-05-18T10:30:00Z",
            },
        )

    monkeypatch.setattr(voice.httpx, "post", fake_post)
    session = VoiceSessionService(
        Settings(
            app_env="test",
            jwt_secret="test-secret-test-secret-test-secret",
            llm_provider="gemini",
            gemini_api_key="gemini-key",
        ),
    ).create_session()

    assert session.provider == "gemini"
    assert session.mode == "realtime"
    assert session.model == "gemini-3.1-flash-live-preview"
    assert session.voice_name == "Kore"
    assert session.ephemeral_token == "ephemeral-token"
    assert session.expires_at == datetime(2026, 5, 18, 10, 30, tzinfo=UTC)

    url, headers, body = calls[0]
    assert url.endswith("/v1alpha/authTokens")
    assert headers["x-goog-api-key"] == "gemini-key"
    auth_token = body["authToken"]
    assert isinstance(auth_token, dict)
    assert auth_token["uses"] == 1
    assert str(auth_token["expireTime"]).endswith("Z")
    assert str(auth_token["newSessionExpireTime"]).endswith("Z")


def test_voice_router_surfaces_provider_failures(monkeypatch: MonkeyPatch) -> None:
    def fake_create_session(self: VoiceSessionService) -> object:
        raise VoiceSessionUnavailableError("Canlı sesli sohbet şu an hazır değil.")

    monkeypatch.setattr(VoiceSessionService, "create_session", fake_create_session)

    with raises(HTTPException) as exc_info:
        create_voice_session(Response(), _current_user=object())  # type: ignore[arg-type]

    assert getattr(exc_info.value, "status_code", None) == 503
    assert getattr(exc_info.value, "detail", None) == "Canlı sesli sohbet şu an hazır değil."
