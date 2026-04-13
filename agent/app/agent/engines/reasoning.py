"""Factory for the main ReasoningAgent (pydantic-ai Agent with tools)."""

from __future__ import annotations

from pydantic_ai import Agent

from app.agent.prompts.agent_prompts import build_system_prompt
from app.agent.utils.model_utils import get_llm
from app.schemas.agent import AgentMode
from app.schemas.language import Language


def build_reasoning_agent(
    mode: AgentMode,
    tools: list,
    language: Language | None = None,
) -> Agent[None, str]:
    """Create a pydantic-ai Agent for the given mode and tool list.

    The agent is stateless — a new instance is created per request so it is
    safe to run from concurrent Celery tasks.
    """
    vendor, model, api_key = get_llm()
    model_str = _model_string(vendor, model)
    system_prompt = build_system_prompt(mode, language)

    agent: Agent[None, str] = Agent(
        model=model_str,
        system_prompt=system_prompt,
        tools=tools,
    )
    return agent


def _model_string(vendor: str, model: str) -> str:
    match vendor:
        case "openai":
            return f"openai:{model}"
        case "google":
            return f"google-gla:{model}"
        case _:  # anthropic default
            return f"anthropic:{model}"
