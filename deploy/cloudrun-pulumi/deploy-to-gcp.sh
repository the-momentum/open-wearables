#!/usr/bin/env bash
set -euo pipefail

STACK="${STACK:-prod}"
PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-europe-west1}"
IMAGE="${IMAGE:?Set IMAGE to the backend container image URI}"
DB_HOST="${DB_HOST:?Set DB_HOST to a PostgreSQL host reachable from Cloud Run}"
DB_NAME="${DB_NAME:-open-wearables}"
DB_USER="${DB_USER:-open-wearables}"
DB_PORT="${DB_PORT:-5432}"
DB_PASSWORD="${DB_PASSWORD:?Set DB_PASSWORD}"
SECRET_KEY="${SECRET_KEY:?Set SECRET_KEY}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@admin.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:?Set ADMIN_PASSWORD}"
SERVICE_NAME="${SERVICE_NAME:-open-wearables}"
FRONTEND_URL="${FRONTEND_URL:-}"
API_BASE_URL="${API_BASE_URL:-}"
CORS_ORIGINS="${CORS_ORIGINS:-}"
VPC_CONNECTOR="${VPC_CONNECTOR:-}"

pulumi stack select "$STACK" 2>/dev/null || pulumi stack init "$STACK"

pulumi config set gcp:project "$PROJECT_ID"
pulumi config set gcp:region "$REGION"
pulumi config set location "$REGION"
pulumi config set serviceName "$SERVICE_NAME"
pulumi config set image "$IMAGE"
pulumi config set dbHost "$DB_HOST"
pulumi config set dbPort "$DB_PORT"
pulumi config set dbName "$DB_NAME"
pulumi config set dbUser "$DB_USER"
pulumi config set adminEmail "$ADMIN_EMAIL"
pulumi config set minInstances 0
pulumi config set maxInstances 4
pulumi config set concurrency 1
pulumi config set timeoutSeconds 600
pulumi config set memory 1Gi
pulumi config set cpu 1
pulumi config set allowUnauthenticated true

pulumi config set --secret dbPassword "$DB_PASSWORD"
pulumi config set --secret secretKey "$SECRET_KEY"
pulumi config set --secret adminPassword "$ADMIN_PASSWORD"

if [[ -n "$FRONTEND_URL" ]]; then
  pulumi config set frontendUrl "$FRONTEND_URL"
fi

if [[ -n "$API_BASE_URL" ]]; then
  pulumi config set apiBaseUrl "$API_BASE_URL"
fi

if [[ -n "$CORS_ORIGINS" ]]; then
  pulumi config set corsOrigins "$CORS_ORIGINS"
fi

if [[ -n "$VPC_CONNECTOR" ]]; then
  pulumi config set vpcConnector "$VPC_CONNECTOR"
fi

pulumi up

echo
echo "Run migrations and seed reference data with:"
pulumi stack output run_init_job
