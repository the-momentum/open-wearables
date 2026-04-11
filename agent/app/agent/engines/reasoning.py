"""Factory for the main ReasoningAgent (pydantic-ai Agent with tools)."""

from __future__ import annotations

from pydantic_ai import Agent

from app.agent.prompts.agent_prompts import AGENT_PROMPT_MAPPING
from app.agent.utils.model_utils import get_llm
from app.schemas.agent import AgentMode


def build_reasoning_agent(mode: AgentMode, tools: list) -> Agent[None, str]:
    """Create a pydantic-ai Agent for the given mode and tool list.

    The agent is stateless — a new instance is created per request so it is
    safe to run from concurrent Celery tasks.
    """
    vendor, model, api_key = get_llm()
    model_str = _model_string(vendor, model)
    system_prompt = AGENT_PROMPT_MAPPING[mode]

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
