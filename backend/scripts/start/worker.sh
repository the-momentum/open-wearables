#!/bin/bash
set -e -x

# Queue list is env-overridable so the same image serves both the general
# worker (default list) and the dedicated fast-lane worker (CELERY_QUEUES=webhook_sync).
uv run celery -A app.main:celery_app worker --loglevel=info --pool=threads -Q "${CELERY_QUEUES:-default,sdk_sync,garmin_sync,webhook_sync}"
