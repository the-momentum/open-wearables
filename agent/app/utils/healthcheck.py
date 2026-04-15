import asyncio

import anthropic
import openai
from fastapi import APIRouter
from google.generativeai.client import configure as genai_configure
from google.generativeai.models import get_model as genai_get_model
from sqlalchemy import text

from app.agent.utils.model_utils import get_llm
from app.config import settings
from app.database import AsyncDbSession, async_engine

healthcheck_router = APIRouter()


def get_pool_status() -> dict[str, str]:
    """Get connection pool status for monitoring."""
    pool = async_engine.pool
    return {
        "max_pool_size": str(pool.size()),  # type: ignore
        "connections_ready_for_reuse": str(pool.checkedin()),  # type: ignore
        "active_connections": str(pool.checkedout()),  # type: ignore
        "overflow": str(pool.overflow()),  # type: ignore
    }


@healthcheck_router.get("/db")
async def database_health(db: AsyncDbSession) -> dict[str, str | dict[str, str]]:
    """Database health check endpoint."""
    try:
        # Test connection
        await db.execute(text("SELECT 1"))

        pool_status = get_pool_status()
        return {
            "status": "healthy",
            "pool": pool_status,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@healthcheck_router.get("/llm")
async def llm_health() -> dict[str, str]:
    """LLM provider health check — sends a minimal request to verify the API is reachable."""
    try:
        vendor, model, api_key = get_llm()
        match vendor:
            case "openai":
                client = openai.OpenAI(api_key=api_key)
                await asyncio.to_thread(client.models.retrieve, model)
            case "google":
                genai_configure(api_key=api_key)
                await asyncio.to_thread(genai_get_model, f"models/{model}")
            case _:  # anthropic
                client = anthropic.Anthropic(api_key=api_key)
                await asyncio.to_thread(client.models.retrieve, model)

        return {
            "status": "healthy",
            "provider": settings.llm_provider,
            "model": model,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "provider": settings.llm_provider,
            "error": str(e),
        }
