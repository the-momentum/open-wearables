#!/usr/bin/env bash
# One-time bootstrap for the ow-staging EC2.
#
# Run this ONCE after attaching the instance profile. Assumes Amazon Linux 2023.
# For Ubuntu, swap `dnf` for `apt-get` and the package names.
#
# Usage (via SSH or SSM):
#   sudo bash bootstrap.sh

set -euo pipefail

log() { printf '\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }

log "Installing Docker + compose plugin..."
if command -v dnf >/dev/null 2>&1; then
  dnf install -y docker
  # docker compose v2 plugin via standalone binary (AL2023 package lags)
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL \
    "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  dnf install -y amazon-ecr-credential-helper || true
else
  apt-get update
  apt-get install -y docker.io docker-compose-plugin amazon-ecr-credential-helper
fi

log "Enabling + starting Docker..."
systemctl enable --now docker

log "Configuring Docker credsStore for ECR (root)..."
mkdir -p /root/.docker
cat > /root/.docker/config.json <<'JSON'
{
  "credsStore": "ecr-login"
}
JSON

log "Creating /app directory..."
mkdir -p /app
chown root:root /app

log "Verifying ECR pull works..."
docker pull 031244176128.dkr.ecr.us-east-1.amazonaws.com/rhiseai/open-wearables-backend:staging 2>&1 || \
  log "  (expected to fail if no :staging tag has been pushed yet — fine)"

log "Bootstrap complete."
