#!/bin/bash
set -e -x

worker_ready() {
    uv run celery -A app.main:celery_app inspect ping
}

until worker_ready; do
  echo 'Celery workers not available...'
  sleep 1
done
echo 'Celery workers are available, proceeding...'

# Flower will use the broker URL from Celery app configuration (settings.redis_url)
uv run celery --app=app.main:celery_app flower
