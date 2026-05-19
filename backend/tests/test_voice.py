"""Tests for voice-chat session bootstrap."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Response
from pytest import MonkeyPatch, raises

from app.config import Settings
from app.routers.voice import create_voice_session
from app.services import voice
from app.services.voice import VoiceSessionService, VoiceSessionUnavailableError


class FakeAuthToken:
    name = "ephemeral-token"


class FakeAuthTokens:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, *, config: object) -> FakeAuthToken:
        self.calls.append({"config": config})
        return FakeAuthToken()


class FakeGenaiClient:
    instances: list[FakeGenaiClient] = []

    def __init__(self, *, api_key: str, http_options: dict[str, str]) -> None:
        self.api_key = api_key
        self.http_options = http_options
        self.auth_tokens = FakeAuthTokens()
        self.instances.append(self)


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
    FakeGenaiClient.instances.clear()
    monkeypatch.setattr(voice.genai, "Client", FakeGenaiClient)
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
    assert session.expires_at is not None
    assert session.expires_at > datetime.now(UTC)

    client = FakeGenaiClient.instances[0]
    assert client.api_key == "gemini-key"
    assert client.http_options == {"api_version": "v1alpha"}
    assert len(client.auth_tokens.calls) == 1
    config = client.auth_tokens.calls[0]["config"]
    assert config.uses == 1
    assert config.http_options.api_version == "v1alpha"
    assert config.expire_time > config.new_session_expire_time


def test_voice_router_surfaces_provider_failures(monkeypatch: MonkeyPatch) -> None:
    def fake_create_session(self: VoiceSessionService) -> object:
        raise VoiceSessionUnavailableError("Canlı sesli sohbet şu an hazır değil.")

    monkeypatch.setattr(VoiceSessionService, "create_session", fake_create_session)

    with raises(HTTPException) as exc_info:
        create_voice_session(Response(), _current_user=object())  # type: ignore[arg-type]

    assert getattr(exc_info.value, "status_code", None) == 503
    assert getattr(exc_info.value, "detail", None) == "Canlı sesli sohbet şu an hazır değil."
