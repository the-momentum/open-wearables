#!/bin/bash
echo '🛑 Stopping Open Wearables...'
docker compose -f docker-compose.local.yml -p open-wearables-local down
echo '✅ Open Wearables stopped.'

