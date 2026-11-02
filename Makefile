DOCKER_COMMAND = docker compose -f docker-compose.yml
DOCKER_EXEC = $(DOCKER_COMMAND) exec app
ALEMBIC_CMD = uv run alembic

FRONTEND_RUN = cd frontend && bun run

help:	## Show this help.
	@echo "============================================================"
	@echo "This is a list of available commands for this project."
	@echo "============================================================"
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

build:	## Builds docker image
	$(DOCKER_COMMAND) build --no-cache

run:	## Runs the environment in detached mode
	$(DOCKER_COMMAND) up -d --force-recreate
	$(DOCKER_COMMAND) rm -f db-svix-init

up:	## Runs the non-detached environment
	$(DOCKER_COMMAND) up --force-recreate

watch:	## Runs the environment with hot-reload
	$(DOCKER_COMMAND) watch

stop:	## Stops running instance
	$(DOCKER_COMMAND) stop

down:	## Kills running instance
	$(DOCKER_COMMAND) down

test:	## Run the tests.
	cd backend && uv run pytest -v --cov=app

migrate:  ## Apply all migrations
	$(DOCKER_EXEC) $(ALEMBIC_CMD) upgrade head

seed:  ## Seed sample data (test users and activity data)
	$(DOCKER_EXEC) uv sync --inexact --group dev --extra otel
	$(DOCKER_EXEC) uv run python scripts/init/seed_activity_data.py

create_migration:  ## Create a new migration. Use 'make create_migration m="Description of the change"'
	@if [ -z "$(m)" ]; then \
		echo "Error: You must provide a migration description using 'm=\"Description\"'"; \
		exit 1; \
	fi
	$(DOCKER_EXEC) $(ALEMBIC_CMD) revision --autogenerate -m "$(m)"

downgrade:  ## Revert the last migration
	$(DOCKER_EXEC) $(ALEMBIC_CMD) downgrade -1

reset_db:  ## Truncate all tables in the database (WARNING: deletes all data)
	$(DOCKER_EXEC) uv run python scripts/reset_database.py

frontend_install:  ## Install frontend dependencies
	cd frontend && bun install --frozen-lockfile

frontend_check:  ## Type-check the frontend
	$(FRONTEND_RUN) check

frontend_lint:  ## Lint the frontend
	$(FRONTEND_RUN) lint

frontend_format:  ## Auto-format the frontend
	$(FRONTEND_RUN) format

frontend_format_check:  ## Check frontend formatting without writing
	$(FRONTEND_RUN) format:check

frontend_test:  ## Run frontend unit and component tests
	$(FRONTEND_RUN) test:unit --run

frontend_test_e2e:  ## Run frontend end-to-end tests (downloads browsers on first run)
	$(FRONTEND_RUN) test:e2e

frontend_verify:  ## Run everything CI runs for the frontend
	$(MAKE) frontend_check frontend_lint frontend_format_check frontend_test frontend_test_e2e
