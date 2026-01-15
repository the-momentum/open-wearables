#!/bin/bash
echo '🗑️  Uninstalling Open Wearables Local...'
echo ''
echo '⏹️  Stopping containers...'
docker compose -f docker-compose.local.yml -p open-wearables-local down -v 2>/dev/null || true
echo '🗄️  Removing Docker volumes...'
docker volume rm open-wearables-local_owlocal_postgres_data open-wearables-local_owlocal_redis_data 2>/dev/null || true
echo '🐳 Removing Docker images...'
docker rmi open-wearables-local:latest open-wearables-frontend-local:dev 2>/dev/null || true
echo '🧹 Cleaning up config files...'
rm -f backend/config/.env.local 2>/dev/null || true
echo ''
echo '✅ Uninstall complete!'
echo ''
echo '💡 To remove this app from Pinokio, right-click → Delete'

