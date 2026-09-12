DOCKER_COMMAND = docker compose -f docker-compose.yml
DOCKER_EXEC = $(DOCKER_COMMAND) exec app
ALEMBIC_CMD = uv run alembic

# Svelte frontend. Targets keep the `svelte-` prefix while both frontends
# exist; rename to `frontend-` once the React app is retired.
SVELTE_DIR = frontend-svelte
SVELTE_RUN = cd $(SVELTE_DIR) && bun run

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
	$(DOCKER_EXEC) uv sync --group dev
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

svelte_install:  ## Install Svelte frontend dependencies
	cd $(SVELTE_DIR) && bun install --frozen-lockfile

svelte_check:  ## Type-check the Svelte frontend
	$(SVELTE_RUN) check

svelte_lint:  ## Lint the Svelte frontend
	$(SVELTE_RUN) lint

svelte_format:  ## Auto-format the Svelte frontend
	$(SVELTE_RUN) format

svelte_format_check:  ## Check Svelte frontend formatting without writing
	$(SVELTE_RUN) format:check

svelte_test:  ## Run Svelte unit and component tests
	$(SVELTE_RUN) test:unit --run

svelte_test_e2e:  ## Run Svelte end-to-end tests (downloads browsers on first run)
	$(SVELTE_RUN) test:e2e

svelte_verify:  ## Run everything CI runs for the Svelte frontend
	$(MAKE) svelte_check svelte_lint svelte_format_check svelte_test svelte_test_e2e
