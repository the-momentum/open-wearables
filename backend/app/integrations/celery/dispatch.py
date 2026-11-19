"""Pluggable task dispatch.

Call sites use :func:`dispatch` instead of ``task.delay(...)`` so the execution
backend can be switched via configuration without touching the call site.

- ``task_execution_mode == "celery"`` (default): enqueue via the broker and return
  the Celery ``AsyncResult``. This is the upstream behaviour.
- ``task_execution_mode == "inline"``: run the task body synchronously in the
  current process and return its value. This removes the need for a Celery worker
  and a Redis broker, enabling a single-service, scale-to-zero deploy.
"""

from typing import Any

from celery import Task

from app.config import settings


def is_inline() -> bool:
    """True when tasks run synchronously in-process (no broker)."""
    return settings.task_execution_mode == "inline"


def dispatch(task: Task, *args: Any, **kwargs: Any) -> Any:
    """Run ``task`` inline or enqueue it, depending on ``task_execution_mode``.

    In inline mode the task body executes synchronously and its return value is
    returned. In celery mode the task is enqueued and the ``AsyncResult`` is
    returned. Callers that need the result (inline) should guard on
    :func:`is_inline`.
    """
    if is_inline():
        return task.run(*args, **kwargs)
    return task.delay(*args, **kwargs)
