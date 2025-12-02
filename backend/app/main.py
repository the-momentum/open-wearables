from logging import INFO, basicConfig
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqladmin import Admin

from app.api import head_router
from app.config import settings
from app.database import engine
from app.integrations.celery import create_celery
from app.integrations.sentry import init_sentry
from app.integrations.sqladmin import add_admin_views
from app.middlewares import add_cors_middleware
from app.utils.exceptions import handle_exception

basicConfig(level=INFO, format="[%(asctime)s - %(name)s] (%(levelname)s) %(message)s")

api = FastAPI(title=settings.api_name)
admin = Admin(app=api, engine=engine)
add_admin_views(admin)
celery_app = create_celery()
init_sentry()

add_cors_middleware(api)

# Mount static files for provider icons
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    api.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@api.get("/")
async def root() -> dict[str, str]:
    return {"message": "Server is running!"}


@api.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> None:
    raise handle_exception(exc, "")


api.include_router(head_router)
