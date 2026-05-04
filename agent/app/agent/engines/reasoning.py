"""Health-domain reasoning agent — wraps pygentic-ai BaseAgent."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic_ai import UsageLimits
from pydantic_ai.messages import ModelMessage
from pydantic_ai.run import AgentRunResult
from pygentic_ai import BaseAgent

from app.agent.deps import HealthAgentDeps
from app.agent.prompts.agent_prompts import build_system_prompt
from app.agent.utils.model_utils import get_llm
from app.config import settings
from app.schemas.agent import AgentMode
from app.schemas.language import LANGUAGE_NAMES, Language


class HealthReasoningAgent(BaseAgent):
    """ReAct-style reasoning agent for the Open Wearables health domain.

    Wraps pygentic-ai BaseAgent with health-specific instructions and
    the configured LLM provider from app settings.

    user_id is stored on the instance and injected into every tool call
    via HealthAgentDeps / RunContext — the model never needs to supply it.
    """

    def __init__(
        self,
        user_id: UUID,
        mode: AgentMode = AgentMode.GENERAL,
        tools: list | None = None,
        language: Language | None = None,
    ) -> None:
        self.user_id = user_id
        vendor, model, api_key = get_llm()
        lang_name = LANGUAGE_NAMES[language] if language else LANGUAGE_NAMES[Language.english]
        instructions = build_system_prompt(mode, language)

        super().__init__(
            llm_vendor=vendor,
            llm_model=model,
            api_key=api_key,
            tool_list=tools or [],
            system_prompt=instructions,
            language=lang_name,
            deps_type=HealthAgentDeps,
            usage_limits=UsageLimits(request_limit=settings.max_tool_calls),
        )

    async def generate_response(
        self,
        query: str,
        chat_history: list[ModelMessage] | None = None,
    ) -> AgentRunResult:
        """Generate response, injecting user_id into deps for tool access."""
        deps = HealthAgentDeps(language=self.language, user_id=self.user_id)
        run_kwargs: dict[str, Any] = {
            "user_prompt": query,
            "message_history": chat_history or [],
            "deps": deps,
        }
        if self.usage_limits:
            run_kwargs["usage_limits"] = self.usage_limits
        return await self.agent.run(**run_kwargs)
