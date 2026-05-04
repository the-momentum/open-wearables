from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import INFO, basicConfig

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.agent.utils.model_utils import validate_llm_config
from app.api import head_router
from app.config import settings
from app.integrations.celery import create_celery
from app.integrations.sentry import init_sentry
from app.middlewares import add_cors_middleware
from app.utils.exceptions import handle_exception
from app.utils.healthcheck import healthcheck_router

basicConfig(level=INFO, format="[%(asctime)s - %(name)s] (%(levelname)s) %(message)s")


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    validate_llm_config()
    yield


api = FastAPI(title=settings.api_name, lifespan=_lifespan)
celery_app = create_celery()
init_sentry()

add_cors_middleware(api)


@api.get("/")
async def root() -> dict[str, str]:
    return {"message": "Server is running!"}


@api.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    http_exc = handle_exception(exc, "")
    return JSONResponse(status_code=http_exc.status_code, content={"detail": http_exc.detail})


api.include_router(head_router, prefix=settings.api_latest)
api.include_router(healthcheck_router, prefix="/health", tags=["health"])
