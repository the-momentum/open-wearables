#!/bin/bash
set -e -x

uv run --frozen --no-sync celery -A app.main:celery_app worker --loglevel=info
