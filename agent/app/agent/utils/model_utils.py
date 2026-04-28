"""Multi-provider LLM factory.

Returns the (llm_vendor, model, api_key) tuple for pygentic-ai agent registration.
Provider is selected via LLM_PROVIDER env var (default: anthropic).
At least one provider API key must be set or a RuntimeError is raised at startup.
"""

from __future__ import annotations


def get_llm(model: str | None = None, is_worker: bool = False) -> tuple[str, str, str]:
    """Return (llm_vendor, model, api_key) for pygentic-ai.

    Args:
        model: Override model name. If None, uses llm_model_workers (is_worker=True)
               or llm_model (is_worker=False) from settings.
        is_worker: Whether this is for a worker agent (router / guardrails / translator).
                   Workers use a cheaper/faster model by default.
    """
    from app.config import settings

    effective_model = model or (settings.llm_model_workers if is_worker else settings.llm_model)
    if effective_model is None:
        raise RuntimeError("No model configured — settings validator failed.")

    match settings.llm_provider:
        case "openai":
            api_key = settings.openai_api_key.get_secret_value()
            if not api_key:
                raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is not set.")
            return "openai", effective_model, api_key

        case "google":
            api_key = settings.google_api_key.get_secret_value()
            if not api_key:
                raise RuntimeError("LLM_PROVIDER=google but GOOGLE_API_KEY is not set.")
            return "google", effective_model, api_key

        case _:  # "anthropic" is the default
            api_key = settings.anthropic_api_key.get_secret_value()
            if not api_key:
                raise RuntimeError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set.")
            return "anthropic", effective_model, api_key


def validate_llm_config() -> None:
    """Validate that a usable LLM provider is configured. Call on startup."""
    get_llm()  # raises RuntimeError if unconfigured
