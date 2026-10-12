#!/bin/bash
set -e -x

scripts/start/install_extensions.sh

rm -f './celerybeat.pid'
uv run celery -A app.main:celery_app beat -l info
