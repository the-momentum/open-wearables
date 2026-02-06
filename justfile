docker_command := "docker compose -f docker-compose.yml"
docker_exec := docker_command + " exec app"
alembic_cmd := "uv run alembic"

# Show this help
help:
    @echo "============================================================"
    @echo "This is a list of available commands for this project."
    @echo "============================================================"
    @just --list

# Build docker image
build:
    {{docker_command}} build --no-cache

# Run the environment in detached mode
run:
    {{docker_command}} up -d --force-recreate

# Run the non-detached environment
up:
    {{docker_command}} up --force-recreate

# Run the environment with hot-reload
watch:
    {{docker_command}} watch

# Run the environment with observability stack (Grafana, Prometheus, Tempo, Loki)
observe:
    {{docker_command}} --profile observability up -d --force-recreate

# Run the environment with hot-reload and observability stack
watch-observe:
    {{docker_command}} --profile observability watch

# Stop running instance
stop:
    {{docker_command}} stop

# Kill running instance
down:
    {{docker_command}} down

# Run the tests
test:
    cd backend && ENV=backend/config/.env.test uv run pytest -v --cov=app

# Apply all migrations
migrate:
    {{docker_exec}} {{alembic_cmd}} upgrade head

# Seed sample data
init:
    {{docker_exec}} uv sync --group dev
    {{docker_exec}} uv run python scripts/init/seed_admin.py
    {{docker_exec}} uv run python scripts/init/seed_series_types.py
    {{docker_exec}} uv run python scripts/init/seed_activity_data.py

# Create a new migration (usage: just create_migration "Description of the change")
create_migration m:
    {{docker_exec}} {{alembic_cmd}} revision --autogenerate -m "{{m}}"

# Revert the last migration
downgrade:
    {{docker_exec}} {{alembic_cmd}} downgrade -1

# Truncate all tables in the database (WARNING: deletes all data)
reset_db:
    {{docker_exec}} uv run python scripts/reset_database.py
