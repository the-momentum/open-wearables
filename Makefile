DOCKER_COMMAND = docker compose -f docker-compose.yml
DOCKER_EXEC = $(DOCKER_COMMAND) exec app
ALEMBIC_CMD = uv run alembic

help:	## Show this help.
	@echo "============================================================"
	@echo "This is a list of available commands for this project."
	@echo "============================================================"
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

build:	## Builds docker image
	$(DOCKER_COMMAND) build --no-cache

run:	## Runs the envionment in detached mode
	$(DOCKER_COMMAND) up -d --force-recreate

up:	## Runs the non-detached environment
	$(DOCKER_COMMAND) up --force-recreate

stop:	## Stops running instance
	$(DOCKER_COMMAND) stop

down:	## Kills running instance
	$(DOCKER_COMMAND) down

test:	## Run the tests.
	export ENV=backend/config/.env.test && \
	cd backend && uv run pytest -v --cov=app

migrate:  ## Apply all migrations
	$(DOCKER_EXEC) $(ALEMBIC_CMD) upgrade head

init:  ## Initialize database (migrations + seed admin user)
	$(DOCKER_EXEC) $(ALEMBIC_CMD) upgrade head
	$(DOCKER_EXEC) uv run python scripts/init/seed_admin.py

create_migration:  ## Create a new migration. Use 'make create_migration m="Description of the change"'
	@if [ -z "$(m)" ]; then \
		echo "Error: You must provide a migration description using 'm=\"Description\"'"; \
		exit 1; \
	fi
	$(DOCKER_EXEC) $(ALEMBIC_CMD) revision --autogenerate -m "$(m)"

downgrade:  ## Revert the last migration
	$(DOCKER_EXEC) $(ALEMBIC_CMD) downgrade -1
