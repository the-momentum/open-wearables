"""Core workflow engine — orchestrates router → reasoning → guardrails pipeline."""

from __future__ import annotations

import logging
from uuid import UUID

from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

from app.agent.engines.guardrails import build_guardrails
from app.agent.engines.reasoning import build_reasoning_agent
from app.agent.engines.router import RouterDecision, build_router
from app.agent.static.default_msgs import GUARDRAILS_REFUSAL_MSG
from app.agent.tools.tool_registry import tool_manager
from app.schemas.agent import AgentMode

logger = logging.getLogger(__name__)


def _build_history(history: list[dict]) -> list[ModelMessage]:
    """Convert stored message dicts to pydantic-ai ModelMessage objects."""
    messages: list[ModelMessage] = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        # assistant messages are returned by the agent naturally; we include
        # only user turns in the seed history to avoid format mismatches
    return messages


class WorkflowEngine:
    """Stateless per-request workflow.

    A new set of agents is instantiated for every call — safe for Celery workers.
    Pipeline: ROUTER → (REASONING + tools) → GUARDRAILS → response string.
    """

    async def run(
        self,
        user_id: UUID,
        message: str,
        history: list[dict],
        mode: AgentMode = AgentMode.GENERAL,
    ) -> str:
        # 1. Route: decide whether to answer or refuse
        router = build_router()
        try:
            router_result = await router.run(message)
            decision: RouterDecision = router_result.data
        except Exception:
            logger.exception("Router failed — defaulting to answer")
            decision = RouterDecision(route="answer", reasoning="router error")

        if decision.route == "refuse":
            logger.info("Message refused: %s", decision.reasoning)
            return GUARDRAILS_REFUSAL_MSG

        # 2. Generate: reasoning agent with tools and conversation history
        tools = tool_manager.get_tools_for_mode(mode)
        reasoning_agent = build_reasoning_agent(mode, tools)
        seed_history = _build_history(history)

        try:
            # Inject user_id into the message context so tools can use it
            augmented_message = f"[user_id={user_id}]\n{message}"
            gen_result = await reasoning_agent.run(augmented_message, message_history=seed_history)
            raw_response: str = str(gen_result.data)
        except Exception:
            logger.exception("Reasoning agent failed")
            raise

        # 3. Guardrails: clean up and format the response
        guardrails = build_guardrails()
        try:
            fmt_result = await guardrails.run(raw_response)
            return str(fmt_result.data)
        except Exception:
            logger.warning("Guardrails failed — returning raw response")
            return raw_response

    async def summarize(self, messages: list[dict]) -> str:
        """Summarize a list of conversation messages into a compact text.

        Used for history compression when the conversation exceeds the threshold.
        Uses the worker (cheaper) model for cost efficiency.
        """
        from app.agent.utils.model_utils import get_llm
        from app.agent.engines.reasoning import _model_string

        vendor, model, _ = get_llm(is_worker=True)
        model_str = _model_string(vendor, model)

        from pydantic_ai import Agent

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
        return str(result.data)


workflow_engine = WorkflowEngine()
