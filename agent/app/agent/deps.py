"""Agent dependency types for pydantic-ai RunContext injection."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from pygentic_ai.engines.base import BaseAgentDeps


@dataclass
class HealthAgentDeps(BaseAgentDeps):
    """Dependencies injected into every tool call via RunContext.

    Extends BaseAgentDeps (which carries language) with the resolved
    user_id so tools never need to receive it as a model-supplied argument.
    """

    user_id: UUID | None = None
