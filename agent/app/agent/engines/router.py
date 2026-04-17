"""Health router agent — wraps pygentic-ai GenericRouter."""

from __future__ import annotations

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pygentic_ai.engines.routers import GenericRouter, RoutingResponse

from app.agent.prompts.worker_prompts import WorkerType, build_worker_prompt
from app.agent.utils.model_utils import get_llm
from app.config import settings


class HealthRouter(GenericRouter):
    """Classifies health assistant messages as answer (1) or refuse (2).

    Wraps pygentic-ai GenericRouter with the health-domain routing prompt
    and the configured worker LLM from app settings.
    Returns pygentic-ai RoutingResponse with route=1 (answer) or route=2 (refuse).

    When ``history`` is provided, the last few turns are prepended to the
    message so the router can correctly classify contextual follow-ups like
    "What can I do to improve it?" after a sleep-data exchange.
    """

    def __init__(self, history: list[ModelMessage] | None = None, language: str = "english") -> None:
        self._history: list[ModelMessage] = history or []

        vendor, model, api_key = get_llm(is_worker=True)
        routing_prompt = build_worker_prompt(WorkerType.ROUTER)

        super().__init__(
            llm_vendor=vendor,
            llm_model=model,
            api_key=api_key,
            routing_prompt=routing_prompt,
            language=language,
        )

    async def route(self, message: str, api_key: str | None = None, logging: bool = False) -> RoutingResponse:
        """Route *message*, optionally enriched with recent conversation context."""
        if not self._history:
            return await super().route(message, api_key=api_key, logging=logging)

        context = self._build_context(message)
        return await super().route(context, api_key=api_key, logging=logging)

    @staticmethod
    def _msg_to_line(msg: ModelMessage) -> list[str]:
        if isinstance(msg, ModelRequest):
            return [f"User: {p.content}" for p in msg.parts if isinstance(p, UserPromptPart)]
        if isinstance(msg, ModelResponse):
            return [f"Assistant: {p.content[:300]}" for p in msg.parts if isinstance(p, TextPart)]
        return []

    def _build_context(self, message: str) -> str:
        """Prepend the last N conversation turns to *message* for the router."""
        recent = self._history[-(settings.router_context_turns * 2) :]
        parts = [line for msg in recent for line in self._msg_to_line(msg)]

        if not parts:
            return message

        context_block = "\n".join(parts)
        return (
            f"[Previous conversation context — use this to classify the current message]\n"
            f"{context_block}\n\n"
            f"Current message: {message}"
        )
