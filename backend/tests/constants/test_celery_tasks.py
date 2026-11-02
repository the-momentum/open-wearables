"""Every Celery task and queue name used by beat, routing, send_task or the workers must be a known one."""

import re
from pathlib import Path
from unittest.mock import patch

from celery import Celery

from app.config import settings
from app.constants.celery_tasks import CeleryQueue, CeleryTask
from app.integrations.celery.core import create_celery


def _celery_app() -> Celery:
    flags = dict.fromkeys(("data_lifecycle_enabled", "ow_scores_enabled", "telemetry_enabled"), True)
    with patch.multiple(settings, **flags):
        celery_app = create_celery()
    celery_app.loader.import_default_modules()
    return celery_app


def test_core_tasks_and_constants_match() -> None:
    registered = {name for name in _celery_app().tasks if name.startswith("app.")}

    assert registered == set(CeleryTask)


def test_beat_schedule_and_routes_use_constants() -> None:
    celery_app = _celery_app()
    beat_tasks = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}

    assert beat_tasks <= set(CeleryTask)
    assert set(celery_app.conf.task_routes) <= set(CeleryTask)
    assert {route["queue"] for route in celery_app.conf.task_routes.values()} <= set(CeleryQueue)


def test_workers_consume_every_queue_and_only_those() -> None:
    worker_script = Path(__file__).resolve().parents[2] / "scripts" / "start" / "worker.sh"
    consumed = {queue for flag in re.findall(r"-Q (\S+)", worker_script.read_text()) for queue in flag.split(",")}

    assert consumed == set(CeleryQueue)
