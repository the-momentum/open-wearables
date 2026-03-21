from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.integrations.task_dispatcher import (
    RegisteredTask,
    deserialize_payload,
    invoke_registered_task,
)

router = APIRouter(prefix="/internal/tasks")


class TaskInvocationPayload(BaseModel):
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


@router.post("/{task_key}")
async def run_internal_task(
    task_key: RegisteredTask,
    payload: TaskInvocationPayload,
) -> dict[str, Any]:
    args = [deserialize_payload(item) for item in payload.args]
    kwargs = {key: deserialize_payload(value) for key, value in payload.kwargs.items()}
    result = invoke_registered_task(task_key, args=args, kwargs=kwargs)
    return {
        "status": "ok",
        "task": task_key.value,
        "result": result,
    }
