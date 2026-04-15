#!/bin/bash
set -e -x

if [ -f /run/svix-secrets/jwt_secret ]; then
    SVIX_JWT_SECRET=$(cat /run/svix-secrets/jwt_secret)
    export SVIX_JWT_SECRET
fi

uv run celery -A app.main:celery_app worker --loglevel=info --pool=threads -Q default,sdk_sync,garmin_sync
