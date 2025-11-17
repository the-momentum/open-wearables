#!/bin/bash
set -e -x

rm -f './celerybeat.pid'
uv run celery -A app.main:celery_app beat -l info
