#!/usr/bin/env bash
# Zero-downtime deploy for OpenWearables on a dedicated EC2.
#
# Called by GH Actions via SSM:
#   bash /app/deploy/scripts/deploy.sh
#
# Prereqs (already ensured by bootstrap):
#   - /app contains the latest deploy/ tree (docker-compose.yml, scripts/)
#   - /app/.env contains OW_IMAGE_BACKEND / OW_IMAGE_FRONTEND and vars referenced
#     by docker-compose.yml
#   - /app/ow.env contains backend provider secrets (loaded via env_file)
#   - Docker configured with ecr-login credential helper so `docker pull` just
#     works against ECR
#
# Strategy:
#   * Pull new images first (fast-fail if ECR is unreachable / tag missing)
#   * Rolling services (app, frontend): scale to N+1, wait healthy, drop old
#   * Background services (celery-worker, celery-beat): in-place restart
#   * Stateful services (db, redis, traefik): never touched unless explicitly
#     requested with FORCE_RESTART_STATEFUL=1

set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
cd "$APP_DIR"

COMPOSE=(docker compose --env-file "$APP_DIR/.env" -f "$APP_DIR/deploy/docker-compose.yml")

ROLLING_SERVICES=(app frontend)
INPLACE_SERVICES=(celery-worker celery-beat)

log() { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[deploy]\033[0m %s\n' "$*" >&2; exit 1; }

log "Ensuring stateful services are up (db, redis, traefik)..."
"${COMPOSE[@]}" up -d db redis traefik

log "Pulling new images..."
"${COMPOSE[@]}" pull "${ROLLING_SERVICES[@]}" "${INPLACE_SERVICES[@]}"

# -----------------------------------------------------------------------------
# Rolling services
# -----------------------------------------------------------------------------
for svc in "${ROLLING_SERVICES[@]}"; do
  log "Rolling $svc..."

  old_ids=$("${COMPOSE[@]}" ps -q "$svc" || true)
  old_count=$(printf '%s\n' "$old_ids" | grep -c . || true)
  new_scale=$((old_count + 1))

  log "  scaling $svc to $new_scale (currently $old_count)"
  "${COMPOSE[@]}" up -d \
    --no-deps --no-recreate --scale "$svc=$new_scale" "$svc"

  # Wait for health: every currently-running container for this service must
  # be "healthy" (or "running" if it has no healthcheck).
  log "  waiting for $svc to become healthy..."
  healthy=0
  for attempt in $(seq 1 60); do
    ids=$("${COMPOSE[@]}" ps -q "$svc")
    [[ -z "$ids" ]] && { sleep 2; continue; }

    unhealthy=0
    while IFS= read -r id; do
      [[ -z "$id" ]] && continue
      state=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null || echo "missing")
      case "$state" in
        healthy|running) ;;
        *) unhealthy=$((unhealthy + 1)) ;;
      esac
    done <<< "$ids"

    if [[ "$unhealthy" -eq 0 ]]; then
      healthy=1
      log "  $svc is healthy"
      break
    fi
    sleep 2
  done
  [[ "$healthy" -eq 1 ]] || die "$svc did not become healthy within 120s"

  # Kill the pre-deploy containers (snapshot taken before scale-up).
  if [[ -n "$old_ids" ]]; then
    log "  removing $old_count old $svc container(s)"
    # shellcheck disable=SC2086
    docker stop --time 30 $old_ids >/dev/null
    # shellcheck disable=SC2086
    docker rm $old_ids >/dev/null
  fi

  # Return to steady state (1 replica).
  "${COMPOSE[@]}" up -d \
    --no-deps --no-recreate --scale "$svc=1" "$svc"
done

# -----------------------------------------------------------------------------
# Background services (no inbound traffic → simple restart is fine)
# -----------------------------------------------------------------------------
for svc in "${INPLACE_SERVICES[@]}"; do
  log "Restarting $svc in place..."
  "${COMPOSE[@]}" up -d --no-deps "$svc"
done

log "Pruning dangling images..."
docker image prune -f >/dev/null

log "Deploy complete."
"${COMPOSE[@]}" ps
