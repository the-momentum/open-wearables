"""Core workflow engine — drives the pygentic-ai user_assistant_graph."""

from __future__ import annotations

import logging
from uuid import UUID

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pygentic_ai import WorkflowState, user_assistant_graph
from pygentic_ai.workflows.nodes import StartNode

from app.agent.engines.guardrails import HealthGuardrailsAgent
from app.agent.engines.reasoning import HealthReasoningAgent
from app.agent.engines.router import HealthRouter
from app.agent.tools.tool_registry import tool_manager
from app.schemas.agent import AgentMode
from app.schemas.language import LANGUAGE_NAMES, Language

logger = logging.getLogger(__name__)


def _build_history(history: list[dict]) -> list[ModelMessage]:
    """Convert stored message dicts to pydantic-ai ModelMessage objects."""
    messages: list[ModelMessage] = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif role == "assistant":
            messages.append(ModelResponse(parts=[TextPart(content=content)]))
    return messages


class WorkflowEngine:
    """Stateless per-request workflow.

    A new set of agents is instantiated for every call — safe for Celery workers.
    Pipeline: ROUTER → (REASONING + tools) → GUARDRAILS → response string,
    orchestrated by the pygentic-ai user_assistant_graph.
    """

    async def run(
        self,
        user_id: UUID,
        message: str,
        history: list[dict],
        mode: AgentMode = AgentMode.GENERAL,
        language: Language | None = None,
    ) -> str:
        lang_name = LANGUAGE_NAMES[language] if language else LANGUAGE_NAMES[Language.english]

        tools = tool_manager.get_tools_for_mode(mode)
        agent = HealthReasoningAgent(user_id=user_id, mode=mode, tools=tools, language=language)
        guardrails = HealthGuardrailsAgent(language=lang_name)

        seed_history = _build_history(history)
        router = HealthRouter(history=seed_history, language=lang_name.lower())

        deps = {
            "agent": agent,
            "router": router,
            "guardrails": guardrails,
            "message": message,
            "chat_history": seed_history,
            # RefuseNode looks up REFUSAL_GENERIC[language] — must be lowercase
            "language": lang_name.lower(),
        }

        state = WorkflowState()
        run_result = await user_assistant_graph.run(StartNode(), state=state, deps=deps)
        return str(run_result.output)

    async def summarize(self, messages: list[dict]) -> str:
        """Summarize a list of conversation messages into a compact text.

        Used for history compression when the conversation exceeds the threshold.
        Uses the worker (cheaper) model for cost efficiency.
        """
        from pydantic_ai import Agent

        from app.agent.utils.model_utils import get_llm

        vendor, model, _ = get_llm(is_worker=True)
        model_str = f"{vendor}:{model}"

        summarizer: Agent[None, str] = Agent(
            model=model_str,
            system_prompt=(
                "You are a conversation summarizer. "
                "Produce a concise factual summary of the health conversation below, "
                "preserving all specific data points (numbers, dates, metrics). "
                "Output only the summary — no preamble."
            ),
        )

        transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        result = await summarizer.run(transcript)
        return str(result.output)


workflow_engine = WorkflowEngine()
