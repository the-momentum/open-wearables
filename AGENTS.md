# Open Wearables

Open Wearables is a health/wearable data aggregation platform with a Python/FastAPI backend and React/TypeScript frontend.

## Documentation Structure

- **This file** - Project overview, development workflow, general guidelines
- **[backend/AGENTS.md](backend/AGENTS.md)** - Backend-specific patterns and code examples
- **[frontend/AGENTS.md](frontend/AGENTS.md)** - Frontend-specific patterns and code examples
- **[docs/dev-guides/how-to-add-new-provider.mdx](docs/dev-guides/how-to-add-new-provider.mdx)** - Adding wearable providers

## Project Structure

```
open-wearables/
├── backend/           # Python/FastAPI backend
├── frontend/          # React/TypeScript frontend
└── docs/              # Documentation (Mintlify)
```

## Tech Stack

| Backend | Frontend |
|---------|----------|
| Python 3.13+ | React 19 + TypeScript |
| FastAPI | TanStack Router/Query |
| SQLAlchemy 2.0 | React Hook Form + Zod |
| PostgreSQL | Tailwind + shadcn/ui |
| Celery + Redis | Vitest |
| Ruff | oxlint + Prettier |

## Development Workflow

### Docker (Recommended)

```bash
# Start all services
docker compose up -d

# Seed sample data (admin@admin.com / secret123)
make init

# View logs
docker compose logs -f app

# Stop
make stop
```

### Access Points
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Celery Flower: http://localhost:5555

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make build` | Build Docker images |
| `make run` | Start in detached mode |
| `make up` | Start in foreground |
| `make stop` | Stop containers |
| `make down` | Remove containers |
| `make test` | Run backend tests |
| `make migrate` | Apply database migrations |
| `make create_migration m="..."` | Create new migration |
| `make init` | Seed sample data |

### Code Quality

**Backend:**
```bash
cd backend && uv run ruff check . --fix && uv run ruff format .
```

**Frontend:**
```bash
cd frontend && pnpm run lint:fix && pnpm run format
```

## Guidelines for AI Agents

1. **Read specialized docs** - See `backend/AGENTS.md` and `frontend/AGENTS.md` for patterns
2. **Never commit secrets** - Check for .env files, API keys, credentials
3. **Follow existing patterns** - Match the code style of surrounding files
4. **Run quality checks** - Always run lint/format after changes
5. **Use type hints** - All Python functions must have type annotations
6. **Test your changes** - Run relevant tests before considering work complete
