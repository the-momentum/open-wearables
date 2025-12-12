from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status

from app.database import DbSession
from app.schemas import UploadDataResponse
from app.services import ApiKeyDep, ae_import_service, hk_import_service

router = APIRouter()


async def get_content_type(request: Request) -> tuple[str, str]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file found")

        if isinstance(file, UploadFile):
            content_bytes = await file.read()
            content_str = content_bytes.decode("utf-8")
        else:
            content_str = str(file)
    else:
        body = await request.body()
        content_str = body.decode("utf-8")

    return content_str, content_type


@router.post("/sdk/users/{user_id}/sync/apple/auto-health-export")
async def sync_data_auto_health_export(
    user_id: str,
    request: Request,
    db: DbSession,
    _api_key: ApiKeyDep,
    content: Annotated[tuple[str, str], Depends(get_content_type)],
) -> UploadDataResponse:
    """Import health data from file upload or JSON."""
    content_str, content_type = content[0], content[1]
    return await ae_import_service.import_data_from_request(db, content_str, content_type, user_id)


@router.post("/sdk/users/{user_id}/sync/apple/healthion")
async def sync_data_healthion(
    user_id: str,
    request: Request,
    db: DbSession,
    _api_key: ApiKeyDep,
    content: Annotated[tuple[str, str], Depends(get_content_type)],
) -> UploadDataResponse:
    """Import health data from file upload or JSON."""
    content_str, content_type = content[0], content[1]
    return await hk_import_service.import_data_from_request(db, content_str, content_type, user_id)
