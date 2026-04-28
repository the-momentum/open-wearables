#!/bin/bash
set -e

# AGENT_DB_NAME must match DB_NAME in agent/config/.env (default: agent)
AGENT_DB="${AGENT_DB_NAME:-agent}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE "$AGENT_DB" OWNER "$POSTGRES_USER";
EOSQL
