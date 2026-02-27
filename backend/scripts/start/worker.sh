#!/bin/bash
set -e -x

uv run celery -A app.main:celery_app worker --loglevel=info --pool=threads -Q default,sdk_sync
