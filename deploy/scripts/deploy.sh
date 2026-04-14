#!/usr/bin/env bash
# Deploy OpenWearables to the dedicated EC2.
#
# Strategy (matches lucie-api/scripts/deploy.sh pattern):
#   1. Pull new images
#   2. Ensure stateful services are up (db, redis, traefik) — idempotent
#   3. Wait for DB to accept connections
#   4. Run alembic upgrade in a THROWAWAY container — if this fails, abort
#      before we touch the live app (avoids the crash-loop we saw in prod)
#   5. Recreate app + frontend with `compose up -d --no-deps` — brief gap,
#      health-polled afterwards
#   6. Bring everything else up (celery-worker, celery-beat)
#   7. Prune dangling images
#
# We deliberately DON'T do scale-based rolling here: the previous version
# left the box in a bad state when the new image crash-looped, because both
# the "new" (never healthy) and "old" containers ended up stuck in
# Restarting. Lucie-api runs a single replica on staging for the same
# reason — the gap is short and recoverable, an unhealthy rollout is not.

set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
cd "$APP_DIR"

COMPOSE=(docker compose --env-file "$APP_DIR/.env" -f "$APP_DIR/deploy/docker-compose.yml")

log() { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[deploy]\033[0m %s\n' "$*" >&2; exit 1; }

# Load .env so we can reference DB vars directly below.
set -a
# shellcheck disable=SC1091
source "$APP_DIR/.env"
set +a

: "${OW_IMAGE_BACKEND:?OW_IMAGE_BACKEND must be set in /app/.env}"
: "${OW_DB_USER:=open-wearables}"
: "${OW_DB_NAME:=open-wearables}"

log "Pulling new images..."
"${COMPOSE[@]}" pull app frontend celery-worker celery-beat

log "Ensuring stateful services are running (db, redis, traefik)..."
"${COMPOSE[@]}" up -d db redis traefik

log "Waiting for database..."
for i in $(seq 1 30); do
  if docker exec ow-db pg_isready -U "$OW_DB_USER" -d "$OW_DB_NAME" >/dev/null 2>&1; then
    log "  db is ready"
    break
  fi
  [[ "$i" -eq 30 ]] && die "database never became ready"
  sleep 2
done

log "Running alembic migrations in a throwaway container..."
if ! docker run --rm \
    --network ow-network \
    --env-file "$APP_DIR/.env" \
    --env-file "$APP_DIR/ow.env" \
    -e DB_HOST=db \
    -e DB_PORT=5432 \
    -e DB_NAME="$OW_DB_NAME" \
    -e DB_USER="$OW_DB_USER" \
    -e DB_PASSWORD="$OW_DB_PASSWORD" \
    -e REDIS_HOST=redis \
    --entrypoint "" \
    "$OW_IMAGE_BACKEND" \
    uv run alembic upgrade head; then
  die "alembic migrations failed — aborting before touching live app"
fi

log "Recreating app + frontend (brief gap)..."
"${COMPOSE[@]}" up -d --no-deps app frontend

log "Health checking app..."
healthy=0
for i in $(seq 1 30); do
  HEALTH=$("${COMPOSE[@]}" ps app --format json 2>/dev/null \
    | jq -sr 'flatten(1) | .[0].Health // "starting"' 2>/dev/null \
    || echo "unknown")
  case "$HEALTH" in
    healthy) healthy=1; log "  app is healthy"; break ;;
    unhealthy) log "  ::warning:: app is UNHEALTHY (attempt $i/30)" ;;
    *) log "  app: $HEALTH ($i/30)" ;;
  esac
  sleep 5
done
[[ "$healthy" -eq 1 ]] || die "app did not become healthy within 150s"

log "Bringing up celery services..."
"${COMPOSE[@]}" up -d --no-deps celery-worker celery-beat

log "Pruning dangling images..."
docker image prune -f >/dev/null

log "Deploy complete."
"${COMPOSE[@]}" ps
