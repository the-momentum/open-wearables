#!/bin/bash
set -e -x

CELERY_BROKER_URL=$(grep '^CELERY_BROKER_URL=' ./config/.env | cut -d '=' -f2- | tr -d '"')

worker_ready() {
    uv run celery -A app.main:celery_app inspect ping
}

until worker_ready; do
  echo 'Celery workers not available...'
  sleep 1
done
echo 'Celery workers are available, proceeding...'

uv run celery --app=app.main:celery_app --broker="$CELERY_BROKER_URL" flower
