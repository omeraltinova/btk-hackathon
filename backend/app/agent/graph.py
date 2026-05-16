"""LangGraph wiring for the Cüzdan Koçu agent."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.agent.prompts import build_system_prompt
from app.agent.tools import TOOLS
from app.config import Settings, get_settings
from app.services.ocr import ascii_header


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    user_role: str
    finance_level: str


LLMProvider = Literal["gemini", "openrouter"]


def build_chat_model(
    *,
    provider: LLMProvider,
    api_key: str,
    model: str,
    openrouter_base_url: str = "https://openrouter.ai/api/v1",
    openrouter_http_referer: str | None = None,
    openrouter_app_title: str | None = None,
) -> BaseChatModel:
    """Build the chat model for the selected provider without binding tools."""
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model,
            api_key=api_key,
            temperature=0.3,
        )

    default_headers: dict[str, str] = {}
    if openrouter_http_referer:
        default_headers["HTTP-Referer"] = ascii_header(openrouter_http_referer)
    if openrouter_app_title:
        default_headers["X-Title"] = ascii_header(openrouter_app_title)

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=openrouter_base_url,
        temperature=0.3,
        default_headers=default_headers or None,
    )


def _api_key_for_settings(settings: Settings) -> str:
    if settings.llm_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY tanımlı değil.")
        return settings.openrouter_api_key
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil.")
    return settings.gemini_api_key


def _model_for_settings(settings: Settings) -> str:
    if settings.llm_provider == "openrouter":
        return settings.openrouter_model
    return settings.gemini_model


def build_agent_graph(
    *,
    api_key: str,
    model: str,
    provider: LLMProvider = "gemini",
    openrouter_base_url: str = "https://openrouter.ai/api/v1",
    openrouter_http_referer: str | None = None,
    openrouter_app_title: str | None = None,
    blocked_tool_names: Iterable[str] = (),
) -> Any:
    """Compile the LangGraph state machine.

    The graph is built lazily by callers so app startup and tests do not require
    an LLM key. Tool wrappers receive `user_id` through `InjectedState`, not
    through the user's prompt. OpenRouter is supported through its
    OpenAI-compatible chat endpoint.
    """
    blocked_names = set(blocked_tool_names)
    tools = [tool_item for tool_item in TOOLS if tool_item.name not in blocked_names]
    llm = build_chat_model(
        provider=provider,
        api_key=api_key,
        model=model,
        openrouter_base_url=openrouter_base_url,
        openrouter_http_referer=openrouter_http_referer,
        openrouter_app_title=openrouter_app_title,
    ).bind_tools(tools)

    def agent_node(state: AgentState) -> dict[str, list[BaseMessage]]:
        system_message = SystemMessage(
            content=build_system_prompt(
                role=state["user_role"],
                level=state["finance_level"],
            ),
        )
        response = llm.invoke([system_message, *list(state["messages"])])
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")
    return workflow.compile()


def build_agent_graph_from_settings(
    settings: Settings | None = None,
    *,
    blocked_tool_names: Iterable[str] = (),
) -> Any:
    """Compile the graph from environment-backed settings."""
    resolved_settings = settings or get_settings()
    return build_agent_graph(
        provider=resolved_settings.llm_provider,
        api_key=_api_key_for_settings(resolved_settings),
        model=_model_for_settings(resolved_settings),
        openrouter_base_url=resolved_settings.openrouter_base_url,
        openrouter_http_referer=resolved_settings.openrouter_http_referer,
        openrouter_app_title=resolved_settings.openrouter_app_title,
        blocked_tool_names=blocked_tool_names,
    )
