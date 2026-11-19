#!/bin/bash
# Serving entrypoint for a single-service, scale-to-zero deploy (e.g. Google Cloud Run).
#
# This starts ONLY the FastAPI app — no Celery worker, no beat, no Flower, no Svix.
# Background work runs inline in the request (task_execution_mode=inline) and the
# app is Redis-free when sync_status_enabled=false and outgoing_webhooks_enabled=false.
#
# Database migrations and one-time seeds are NOT run here so cold starts stay fast —
# run scripts/start/init_cloudrun.sh once per deploy (e.g. as a Cloud Run Job) instead.
#
# Cloud Run provides the port to listen on via $PORT (default 8080).
set -e

exec uv run fastapi run app/main.py --host 0.0.0.0 --port "${PORT:-8080}"
