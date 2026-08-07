from pydantic import BaseModel


class TaskDispatchResponse(BaseModel):
    """Response for an endpoint that dispatches a background (Celery) task."""

    task_id: str
    status: str
