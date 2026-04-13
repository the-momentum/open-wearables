"""Guardrails agent — formats and cleans raw reasoning-agent output."""

from __future__ import annotations

from pydantic_ai import Agent

from app.agent.engines.reasoning import _model_string
from app.agent.prompts.worker_prompts import build_guardrails_prompt
from app.agent.utils.model_utils import get_llm

_DEFAULT_SOFT_WORD_LIMIT = 150


def build_guardrails(
    language: str = "English",
    soft_word_limit: int | None = _DEFAULT_SOFT_WORD_LIMIT,
) -> Agent[None, str]:
    """Create a lightweight formatting agent using the worker model.

    Args:
        language: ISO 639 language name or code for the response language.
        soft_word_limit: Approximate max word count. Pass ``None`` to allow
            the agent to return the full response without length throttling.
    """
    vendor, model, _ = get_llm(is_worker=True)
    model_str = _model_string(vendor, model)
    return Agent(
        model=model_str,
        system_prompt=build_guardrails_prompt(language=language, soft_word_limit=soft_word_limit),
    )
