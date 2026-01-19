from pydantic import BaseModel


class UploadDataResponse(BaseModel):
    status_code: int
    response: str
    user_id: str | None = None
