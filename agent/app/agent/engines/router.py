"""Router agent — classifies incoming user messages as answer/refuse."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent

from app.agent.engines.reasoning import _model_string
from app.agent.prompts.worker_prompts import ROUTER_SYSTEM_PROMPT
from app.agent.utils.model_utils import get_llm


class RouterDecision(BaseModel):
    route: Literal["answer", "refuse"]
    reasoning: str


def build_router() -> Agent[None, RouterDecision]:
    """Create a lightweight router agent using the worker model."""
    vendor, model, _ = get_llm(is_worker=True)
    model_str = _model_string(vendor, model)
    return Agent(
        model=model_str,
        system_prompt=ROUTER_SYSTEM_PROMPT,
        result_type=RouterDecision,
    )
