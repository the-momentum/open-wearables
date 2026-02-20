#!/bin/bash
set -e

echo '🔧 Checking Docker installation...'
docker --version || { echo '❌ Docker not found! Please install Docker Desktop first.'; exit 1; }

echo '📁 Setting up environment files...'
cp backend/config/.env.local.template backend/config/.env.local

echo '🔑 Generating secure secret key...'
node scripts/pinokio/generate-secrets.js

echo '🐳 Building Docker images (this may take a few minutes)...'
docker compose -f docker-compose.local.yml -p open-wearables-local build

echo ''
echo '✅ Installation complete! Click Start to launch Open Wearables.'

