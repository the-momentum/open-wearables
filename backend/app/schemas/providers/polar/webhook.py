from pydantic import BaseModel


class PolarWebhookEvent(BaseModel):
    event: str
    user_id: str | None = None
    entity_id: str | None = None
    timestamp: str | None = None
    url: str | None = None
