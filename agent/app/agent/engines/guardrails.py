"""Guardrails agent — formats and cleans raw reasoning-agent output."""

from __future__ import annotations

from pydantic_ai import Agent

from app.agent.engines.reasoning import _model_string
from app.agent.prompts.worker_prompts import GUARDRAILS_SYSTEM_PROMPT
from app.agent.utils.model_utils import get_llm


def build_guardrails() -> Agent[None, str]:
    """Create a lightweight formatting agent using the worker model."""
    vendor, model, _ = get_llm(is_worker=True)
    model_str = _model_string(vendor, model)
    return Agent(
        model=model_str,
        system_prompt=GUARDRAILS_SYSTEM_PROMPT,
    )
