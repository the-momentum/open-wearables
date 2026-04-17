"""Health guardrails agent — wraps pygentic-ai GuardrailsAgent."""

from __future__ import annotations

from pygentic_ai.engines.guardrails import GuardrailsAgent

from app.agent.prompts.worker_prompts import WorkerType, build_worker_prompt
from app.agent.utils.model_utils import get_llm
from app.config import settings


class HealthGuardrailsAgent(GuardrailsAgent):
    """Output formatter and validator for health assistant responses.

    Wraps pygentic-ai GuardrailsAgent with health-domain formatting
    rules and the configured worker LLM from app settings.
    """

    def __init__(
        self,
        language: str = "English",
        soft_word_limit: int | None = None,
    ) -> None:
        if soft_word_limit is None:
            soft_word_limit = settings.guardrails_soft_word_limit
        vendor, model, api_key = get_llm(is_worker=True)
        prompt = build_worker_prompt(
            WorkerType.GUARDRAILS,
            language=language,
            soft_word_limit=soft_word_limit,
        )

        super().__init__(
            llm_vendor=vendor,
            llm_model=model,
            api_key=api_key,
            system_prompt=prompt,
            language=language,
        )
