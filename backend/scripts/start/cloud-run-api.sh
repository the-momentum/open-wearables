#!/bin/bash
set -e -x

PORT="${PORT:-8000}"

echo "Starting the FastAPI application for Cloud Run..."
/opt/venv/bin/fastapi run app/main.py --host 0.0.0.0 --port "${PORT}"
