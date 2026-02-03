#!/bin/bash
echo '⚠️  This will delete all data and reset the database!'
echo 'Stopping services...'
docker compose -f docker-compose.local.yml -p open-wearables-local down -v
echo '🗑️  Removing Docker volumes...'
docker volume rm open-wearables-local_owlocal_postgres_data open-wearables-local_owlocal_redis_data 2>/dev/null || true
echo '✅ Database reset complete. Click Start to reinitialize.'

