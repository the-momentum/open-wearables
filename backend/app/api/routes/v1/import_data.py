from fastapi import APIRouter, Depends, Request

from app.services import ae_import_service, hk_import_service, ApiKeyDep
from app.schemas import UploadDataResponse
from app.database import DbSession
from typing import Annotated


router = APIRouter()


async def get_content_type(request: Request) -> tuple[str, str]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file:
            return UploadDataResponse(response="No file found")

        content_str = await file.read()
        content_str = content_str.decode("utf-8")
    else:
        body = await request.body()
        content_str = body.decode("utf-8")

    return content_str, content_type


@router.post("/users/{user_id}/import/apple/auto-health-export")
async def import_data_auto_health_export(
    user_id: str,
    request: Request,
    db: DbSession,
    _api_key: ApiKeyDep,
    content: Annotated[tuple[str, str], Depends(get_content_type)],
) -> UploadDataResponse:
    """Import health data from file upload or JSON."""
    content_str, content_type = content[0], content[1]
    return await ae_import_service.import_data_from_request(db, content_str, content_type, user_id)


@router.post("/users/{user_id}/import/apple/healthion")
async def import_data_healthion(
    user_id: str,
    request: Request,
    db: DbSession,
    _api_key: ApiKeyDep,
    content: Annotated[tuple[str, str], Depends(get_content_type)],
) -> UploadDataResponse:
    """Import health data from file upload or JSON."""
    content_str, content_type = content[0], content[1]
    return await hk_import_service.import_data_from_request(db, content_str, content_type, user_id)
