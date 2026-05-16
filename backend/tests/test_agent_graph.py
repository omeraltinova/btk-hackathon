from __future__ import annotations

import pytest
from langchain_openai import ChatOpenAI

from app.agent.graph import build_agent_graph_from_settings, build_chat_model
from app.agent.tools import TOOLS
from app.config import Settings


def test_openrouter_chat_model_uses_openai_compatible_endpoint_and_headers() -> None:
    model = build_chat_model(
        provider="openrouter",
        api_key="sk-or-test",
        model="google/gemini-3.1-flash-lite",
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_http_referer="http://localhost:3000",
        openrouter_app_title="Cüzdan Koçu",
    )

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "google/gemini-3.1-flash-lite"
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


def test_agent_tool_registry_includes_custom_lesson_tool() -> None:
    assert "create_custom_lesson" in {tool.name for tool in TOOLS}


def test_agent_tool_registry_includes_goal_and_envelope_crud_tools() -> None:
    tool_names = {tool.name for tool in TOOLS}

    assert {
        "create_saving_goal",
        "create_accumulation_goal",
        "get_saving_goals",
        "update_saving_goal",
        "delete_saving_goal",
        "get_envelopes",
        "create_envelope_budget",
        "update_envelope_budget",
        "delete_envelope_budget",
    } <= tool_names


def test_build_agent_graph_can_block_tools_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_tool_names: list[str] = []

    class FakeModel:
        def bind_tools(self, tools: list[object]) -> FakeModel:
            captured_tool_names.extend(getattr(tool, "name") for tool in tools)
            return self

        def invoke(self, _messages: object) -> object:
            raise AssertionError("Graph should not be invoked in this unit test")

    monkeypatch.setattr(
        "app.agent.graph.build_chat_model",
        lambda **_kwargs: FakeModel(),
    )

    from app.agent.graph import build_agent_graph

    build_agent_graph(
        api_key="test",
        model="test-model",
        blocked_tool_names={"create_saving_goal", "delete_envelope_budget"},
    )

    assert "create_saving_goal" not in captured_tool_names
    assert "delete_envelope_budget" not in captured_tool_names
    assert "get_spending" in captured_tool_names
