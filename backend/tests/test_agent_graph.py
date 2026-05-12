from __future__ import annotations

import pytest
from langchain_openai import ChatOpenAI

from app.agent.graph import build_agent_graph_from_settings, build_chat_model
from app.config import Settings


def test_openrouter_chat_model_uses_openai_compatible_endpoint_and_headers() -> None:
    model = build_chat_model(
        provider="openrouter",
        api_key="sk-or-test",
        model="google/gemini-2.5-flash",
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_http_referer="http://localhost:3000",
        openrouter_app_title="Cüzdan Koçu",
    )

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "google/gemini-2.5-flash"
    assert str(model.openai_api_base) == "https://openrouter.ai/api/v1"
    assert model.default_headers == {
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Cuzdan Kocu",
    }


def test_build_agent_graph_from_settings_requires_openrouter_key() -> None:
    settings = Settings(
        llm_provider="openrouter",
        openrouter_api_key=None,
        gemini_api_key=None,
    )

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        build_agent_graph_from_settings(settings)


def test_build_agent_graph_from_settings_requires_gemini_key_by_default() -> None:
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key=None,
        openrouter_api_key=None,
    )

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        build_agent_graph_from_settings(settings)
