# Open Wearables Agent

The AI health assistant service for the Open Wearables platform. It wraps a three-stage LLM pipeline (router → reasoning → guardrails) and delivers answers to natural-language questions about a user's wearable data via an async Celery task and HTTP callback.

The agent reads health data from the Open Wearables backend using the same REST API the frontend uses. It never stores health data itself.

---

## How it fits into the platform

```
Frontend → POST /api/v1/chat → Agent (port 8001)
                                    ↓ Celery task
                               Reasoning + tool calls
                                    ↓ GET /api/v1/users/{id}/...
                               OW Backend (port 8000)
                                    ↓ POST callback_url
                               Your application
```

The agent is **opt-in** — it runs under the `agent` Docker Compose profile so it does not start by default.

---

## Prerequisites

- The **Open Wearables backend** must be running and healthy (`http://localhost:8000`)
- An **LLM API key** for at least one of: Anthropic, OpenAI, or Google
- The agent's `OW_API_KEY` must match the `AGENT_API_KEY` configured in the backend (both default to `sk-agent-default-key` in development — the backend auto-seeds this on startup)
- The agent's `SECRET_KEY` must match the backend's `SECRET_KEY` so JWT tokens issued by the backend are valid when presented to the agent

---

## Docker setup (recommended)

The agent runs as three containers sharing the same image: the FastAPI app, a Celery worker, and a Celery beat scheduler. All three must be running for the full pipeline to work.

### 1. Create the env file

```bash
cp agent/config/.env.example agent/config/.env
```

Open `agent/config/.env` and fill in at minimum:

```bash
# Must match backend/config/.env SECRET_KEY exactly
SECRET_KEY=your-jwt-secret

# LLM provider — set the key for whichever provider you choose
LLM_PROVIDER=anthropic          # anthropic | openai | google
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=...

# Leave as-is for local dev (backend seeds this key automatically)
OW_API_KEY=sk-agent-default-key
```

All other values work out of the box with the default Docker Compose setup.

### 2. Start the backend first

```bash
# From the repo root
docker compose up -d
```

Wait for the backend to be healthy (`docker compose ps` shows `(healthy)` for `app`).

### 3. Start the agent services

```bash
docker compose --profile agent up -d
```

This starts:

| Container | Role | Internal port |
|-----------|------|---------------|
| `agent__open-wearables` | FastAPI app, runs migrations on startup | 8001 |
| `agent-celery-worker__open-wearables` | Processes `process_message` tasks | — |
| `agent-celery-beat__open-wearables` | Runs the `manage-conversation-lifecycle` beat task every 5 min | — |

### 4. Verify

```bash
curl http://localhost:8001/health/db
# → {"status":"healthy","pool":{"max_pool_size":"5","connections_ready_for_reuse":"1","active_connections":"0","overflow":"0"}}
```

API docs: http://localhost:8001/docs

---

## Configuration

All settings are read from `agent/config/.env` via `pydantic-settings`. The full list is in `app/config.py`; the key variables are:

| Variable | Default | Notes |
|----------|---------|-------|
| `SECRET_KEY` | *(required)* | **Must match** the OW backend's `SECRET_KEY` |
| `LLM_PROVIDER` | `anthropic` | `anthropic` / `openai` / `google` |
| `LLM_MODEL` | *(provider default)* | Main reasoning model — see defaults below |
| `LLM_MODEL_WORKERS` | *(provider default)* | Router / guardrails / summariser model |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` |
| `GOOGLE_API_KEY` | — | Required when `LLM_PROVIDER=google` |
| `OW_API_URL` | `http://app:8000` | Backend URL — `app` resolves inside Docker; use `http://localhost:8000` for local dev |
| `OW_API_KEY` | `sk-agent-default-key` | Must match `AGENT_API_KEY` in `backend/config/.env` |
| `DB_HOST` | `db` | Overridden to `db` by Docker Compose; change to `localhost` for local dev |
| `DB_NAME` | `agent` | Agent has its own database, separate from the backend |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Use `redis://localhost:6379/0` for local dev |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` | |
| `SESSION_TIMEOUT_MINUTES` | `10` | Idle minutes before a session is deactivated |
| `CONVERSATION_CLOSE_HOURS` | `24` | Hours idle before a conversation is archived |
| `HISTORY_SUMMARY_THRESHOLD` | `20` | Messages before history is compressed |
| `MAX_TOOL_CALLS` | `10` | Tool calls allowed per reasoning turn |
| `GUARDRAILS_SOFT_WORD_LIMIT` | `150` | Approximate word cap on agent responses |

### LLM model defaults per provider

| Provider | `LLM_MODEL` | `LLM_MODEL_WORKERS` |
|----------|-------------|---------------------|
| `anthropic` | `claude-sonnet-4-6` | `claude-haiku-4-5-20251001` |
| `openai` | `gpt-5` | `gpt-5-mini` |
| `google` | `gemini-2.0-flash` | `gemini-2.0-flash-lite` |

---

## Wiring the backend API key

The agent authenticates to the backend using `X-Open-Wearables-API-Key`. This key is seeded automatically into the backend's `api_key` table on startup via `backend/scripts/init/seed_agent_api_key.py`.

In **development** both sides default to `sk-agent-default-key` — no action needed.

In **production** set the same value in both places:

```bash
# backend/config/.env
AGENT_API_KEY=your-secure-random-key

# agent/config/.env
OW_API_KEY=your-secure-random-key
```

---

## API quick reference

All endpoints require a valid JWT in `Authorization: Bearer <token>`. The token must be issued by the OW backend (`POST /api/v1/auth/login` or `POST /api/v1/users/{id}/token`) and signed with the shared `SECRET_KEY`.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/conversation` | Create a new conversation (returns `conversation_id`) |
| `PATCH` | `/api/v1/conversation/{id}` | Deactivate the active session |
| `POST` | `/api/v1/chat/{conversation_id}` | Send a message — requires `message` and `callback_url` |
| `GET` | `/health/db` | Health check |

The chat endpoint is **async**: it returns a `task_id` immediately and POSTs the agent's response to your `callback_url` when the Celery task completes.

See the [Agent Developer Guide](../docs/dev-guides/agent-architecture.mdx) for full request/response shapes.

---

## Database migrations

The agent manages its own `agent` database (separate from the backend's `open-wearables` database). Migrations run automatically on container startup.

To create a new migration after changing a model:

```bash
# Docker
docker compose --profile agent exec agent \
    uv run alembic revision --autogenerate -m "describe the change"

# Local
uv run alembic revision --autogenerate -m "describe the change"
```

Apply manually if needed:

```bash
docker compose --profile agent exec agent uv run alembic upgrade head
```

---

## Local development (without Docker)

You still need PostgreSQL and Redis running. Update `agent/config/.env`:

```bash
DB_HOST=localhost
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
OW_API_URL=http://localhost:8000
```

Then:

```bash
cd agent

# Install dependencies
uv sync

# Apply migrations
uv run alembic upgrade head

# Start the API server (hot-reload)
uv run fastapi dev app/main.py --host 0.0.0.0 --port 8001

# In a second terminal — start the Celery worker
uv run celery -A app.main:celery_app worker --loglevel=info

# In a third terminal — start the beat scheduler (conversation lifecycle)
uv run celery -A app.main:celery_app beat --loglevel=info
```

---

## Running tests

The test suite has two tiers:

**Agent unit tests** (`tests/agent/`) — pure unit tests with all I/O mocked. Run without Docker:

```bash
cd agent
uv run pytest tests/agent/ -v
```

**Full suite** — needs PostgreSQL (via Docker or `TEST_DATABASE_URL`):

```bash
# Using testcontainers (Docker must be running)
uv run pytest -v

# Using an existing Postgres instance (faster)
TEST_DATABASE_URL=postgresql+psycopg://open-wearables:open-wearables@localhost:5432/agent_test \
    uv run pytest -v

# With coverage
uv run pytest --cov=app --cov-report=term-missing
```

Run pre-commit and type checks:

```bash
uv run pre-commit run --all-files
uv run ty check app/
```

---

## Hot-reload in Docker

`docker compose watch` syncs local file changes into the running containers without a full rebuild:

```bash
docker compose --profile agent watch
```

- Changes to `agent/app/` sync instantly
- Changes to `agent/config/.env` or `agent/migrations/` restart the container
- Changes to `agent/uv.lock` trigger a rebuild
