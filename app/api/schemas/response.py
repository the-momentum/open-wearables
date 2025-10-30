from pydantic import BaseModel


class UploadDataResponse(BaseModel):
    status_code: int
    response: str
