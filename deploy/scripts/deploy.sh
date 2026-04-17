#!/usr/bin/env bash
# Deploy OpenWearables with zero-downtime rolling updates.
#
# Strategy:
#   1. Pull new images
#   2. Ensure stateful services are up (db, redis, traefik, svix-server) — idempotent
#   3. Wait for DB to accept connections
#   4. Run alembic upgrade in a THROWAWAY container — abort if it fails,
#      before touching any live service
#   5. For each ROLLING service (app, frontend, celery-worker):
#        - Snapshot currently-running container IDs
#        - Scale N → N+1 (new container starts alongside old)
#        - Wait for the NEW container to become healthy
#        - On timeout → rollback: stop the NEW container, scale back
#        - On success → stop the OLD container(s) by snapshot ID,
#          then scale back to 1 (steady state)
#      Traefik LBs across all healthy containers via Docker discovery,
#      so the service is continuously reachable.
#   6. Restart celery-beat in place (singleton — brief gap is acceptable
#      since beat has no inbound traffic)
#   7. Prune dangling images
#
# Zero-downtime holds for: app, frontend, celery-worker
# Brief gap on: celery-beat (scheduler), db/redis/traefik (not touched)
#
# Preconditions (enforced by compose file):
#   * Rolling services must NOT set container_name
#   * Rolling services must have a healthcheck
#   * stop_grace_period should be long enough to finish in-flight work

set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
cd "$APP_DIR"

COMPOSE=(docker compose --env-file "$APP_DIR/.env" -f "$APP_DIR/deploy/docker-compose.yml")

ROLLING_SERVICES=(app frontend celery-worker)
SINGLETON_SERVICES=(celery-beat)

HEALTH_TIMEOUT_SECONDS=240   # 4 min — covers start_period + slow starts
HEALTH_POLL_INTERVAL=5

log()  { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[deploy]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[deploy]\033[0m %s\n' "$*" >&2; exit 1; }

# Load .env so we can reference DB vars directly.
set -a
# shellcheck disable=SC1091
source "$APP_DIR/.env"
set +a

: "${OW_IMAGE_BACKEND:?OW_IMAGE_BACKEND must be set in /app/.env}"
: "${OW_DB_USER:=open-wearables}"
: "${OW_DB_NAME:=open-wearables}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Get the per-container Docker health state.
# Returns: healthy | unhealthy | starting | running | exited | missing
container_state() {
  local id=$1
  docker inspect -f \
    '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
    "$id" 2>/dev/null || echo "missing"
}

# Wait until every listed container ID reports healthy.
# Services without a healthcheck are accepted on "running" AFTER a minimum
# warmup period to avoid flapping on startup.
#
# Args: timeout_seconds "id1 id2 ..."
wait_containers_healthy() {
  local timeout=$1; shift
  local ids=$1
  local started=$SECONDS
  local all_good=0

  while (( SECONDS - started < timeout )); do
    all_good=1
    for id in $ids; do
      state=$(container_state "$id")
      case "$state" in
        healthy)
          : ;;
        running)
          # No healthcheck case — accept after 20s warmup. This branch
          # should never fire for our services (all have healthchecks),
          # but it's a safety net.
          if (( SECONDS - started < 20 )); then all_good=0; fi
          ;;
        *)
          all_good=0
          ;;
      esac
    done
    if (( all_good == 1 )); then
      return 0
    fi
    sleep "$HEALTH_POLL_INTERVAL"
  done
  return 1
}

# Roll a single service with zero-downtime.
roll_service() {
  local svc=$1

  log "Rolling $svc..."

  # Snapshot the currently-running containers for this service.
  # `ps -q` lists IDs, one per line.
  local old_ids
  old_ids=$("${COMPOSE[@]}" ps -q "$svc" 2>/dev/null || true)
  local old_count
  old_count=$(printf '%s\n' "$old_ids" | grep -c . || true)
  local new_scale=$((old_count + 1))

  log "  $svc: $old_count old → scaling to $new_scale"

  # --no-recreate: don't touch existing containers, just add one more.
  "${COMPOSE[@]}" up -d --no-deps --no-recreate \
    --scale "$svc=$new_scale" "$svc"

  # Find the newly-created container(s): current IDs minus old IDs.
  local all_ids
  all_ids=$("${COMPOSE[@]}" ps -q "$svc")
  local new_ids
  new_ids=$(comm -23 \
    <(printf '%s\n' "$all_ids" | sort) \
    <(printf '%s\n' "$old_ids" | sort) \
    | tr '\n' ' ')
  new_ids=${new_ids% }

  if [[ -z "$new_ids" ]]; then
    die "$svc: could not identify new container after scale-up"
  fi

  log "  $svc: new container(s): $new_ids — waiting up to ${HEALTH_TIMEOUT_SECONDS}s"

  if ! wait_containers_healthy "$HEALTH_TIMEOUT_SECONDS" "$new_ids"; then
    warn "  $svc: new container did not become healthy — ROLLING BACK"

    # Rollback: stop + remove the NEW containers, leave OLD running.
    for id in $new_ids; do
      docker stop --time 30 "$id" >/dev/null 2>&1 || true
      docker rm "$id" >/dev/null 2>&1 || true
    done
    "${COMPOSE[@]}" up -d --no-deps --no-recreate \
      --scale "$svc=$old_count" "$svc"

    die "$svc rollout failed — old containers remain in service"
  fi

  log "  $svc: new container(s) healthy — draining old"

  if [[ -n "$old_ids" ]]; then
    # stop_grace_period from compose gives the old container time to
    # finish in-flight work (HTTP requests, celery tasks).
    for id in $old_ids; do
      docker stop "$id" >/dev/null 2>&1 || true
      docker rm "$id" >/dev/null 2>&1 || true
    done
  fi

  # Return to steady-state scale of 1.
  "${COMPOSE[@]}" up -d --no-deps --no-recreate \
    --scale "$svc=1" "$svc"

  log "  $svc: done"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

log "Pulling new images..."
"${COMPOSE[@]}" pull "${ROLLING_SERVICES[@]}" "${SINGLETON_SERVICES[@]}"

log "Ensuring stateful services are running (db, redis, traefik, svix-server)..."
"${COMPOSE[@]}" up -d db redis traefik svix-server

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
# Use `compose run` (not `docker run`) so the compose project's network,
# env_file merging, and service config are reused automatically. The
# network is named `<project>_ow-network` at runtime, not `ow-network`.
if ! "${COMPOSE[@]}" run --rm --no-deps \
    --entrypoint "" \
    app \
    uv run alembic upgrade head; then
  die "alembic migrations failed — aborting before touching live services"
fi

# --- Rolling services (zero-downtime) --------------------------------------
for svc in "${ROLLING_SERVICES[@]}"; do
  roll_service "$svc"
done

# --- Singletons (brief gap, not user-visible) ------------------------------
for svc in "${SINGLETON_SERVICES[@]}"; do
  log "Restarting singleton: $svc (brief gap acceptable)"
  "${COMPOSE[@]}" up -d --no-deps --force-recreate "$svc"
done

log "Pruning dangling images..."
docker image prune -f >/dev/null

log "Deploy complete."
"${COMPOSE[@]}" ps
