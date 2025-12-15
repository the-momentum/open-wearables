# Open Wearables

Open Wearables is a health/wearable data aggregation platform with a Python/FastAPI backend and React/TypeScript frontend.

## Project Structure

- `backend/` - FastAPI Python backend (API, services, repositories, models)
- `frontend/` - React/TypeScript frontend (TanStack Router, shadcn/ui)
- `docs/` - Documentation site (Mintlify)

## Backend (Python)

### Prerequisites
- Python 3.13+
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Code Style

- **Line length**: 120 characters
- **Type hints**: Required on all functions (parameters and return types)
- **Imports**: Sorted by isort rules (stdlib → third-party → local)
- **Naming**: Follow PEP 8 conventions (snake_case for functions/variables, PascalCase for classes)

### Ruff Linting Rules

The project enforces these Ruff rules (configured in `backend/pyproject.toml`):
- `I` - isort (import sorting)
- `F` - pyflakes (undefined names, unused imports)
- `FAST` - FastAPI best practices
- `ANN` - flake8-annotations (type hints required)
- `ASYNC` - flake8-async (async/await correctness)
- `COM` - flake8-commas
- `T10` - flake8-debugger (no debug statements)
- `PT` - flake8-pytest-style (pytest conventions)
- `RET` - flake8-return (explicit returns)
- `SIM` - flake8-simplify (code simplification)
- `N` - pep8-naming
- `E`, `W` - pycodestyle errors and warnings

### Architecture Patterns

The backend follows a layered architecture:
```
Routes (app/api/routes/) → Services (app/services/) → Repositories (app/repositories/) → Models (app/models/)
```

- **Routes**: API endpoint handlers, request validation
- **Services**: Business logic, orchestration
- **Repositories**: Database queries, data access
- **Models**: SQLAlchemy ORM models

### Provider Strategy Pattern

Provider integrations use Strategy + Factory patterns in `backend/app/services/providers/`:

```
providers/
├── base_strategy.py      # Abstract base class
├── factory.py            # Provider instantiation
├── garmin/
│   ├── strategy.py       # GarminStrategy
│   ├── oauth.py          # OAuth handler
│   └── workouts.py       # Data sync handler
├── polar/
├── suunto/
└── apple/
```

When adding a new provider, follow the guide in `docs/dev-guides/how-to-add-new-provider.mdx`.

### Database Migrations

- Uses Alembic for migrations (files in `backend/migrations/`)
- Create migration: `make create_migration m="Description"`
- Apply migrations: `make migrate`
- Rollback: `make downgrade`

### Running Commands

Always run code quality checks after making backend changes:

```bash
cd backend

# Lint check
uv run ruff check .

# Auto-fix lint issues
uv run ruff check . --fix

# Format check
uv run ruff format . --check

# Auto-format
uv run ruff format .

# Type check
uv run ty check .

# Run all pre-commit hooks
uv run pre-commit run --all-files
```

Run `uv run ruff check . --fix && uv run ruff format .` automatically after making Python code changes; do not ask for approval to run it.

### Testing

- Framework: pytest with pytest-asyncio
- Run tests: `make test` or `cd backend && uv run pytest -v --cov=app`
- Test config: `backend/config/.env.test`

#### Test Conventions
- Use `pytest.mark.asyncio` for async tests
- Use `faker` for generating test data
- Prefer comparing entire objects over individual fields
- Place test files alongside source files or in `tests/` directory

---

## Frontend (TypeScript/React)

### Prerequisites
- Node.js 22+
- pnpm 10+ (`corepack enable && corepack prepare pnpm@latest --activate`)

### Code Style

- **Line width**: 80 characters
- **Quotes**: Single quotes
- **Semicolons**: Always use
- **Trailing commas**: ES5 style
- **Indentation**: 2 spaces
- **TypeScript**: Strict mode enabled

### Linting & Formatting

**oxlint** for linting (configured in `frontend/.oxlintrc.json`):
- No console.log/debugger in production code
- No explicit `any` types (except in test files)
- React self-closing components preferred

**Prettier** for formatting (configured in `frontend/prettier.config.mjs`)

### Running Commands

```bash
cd frontend

# Lint
pnpm run lint

# Auto-fix lint issues
pnpm run lint:fix

# Format check
pnpm run format:check

# Auto-format
pnpm run format

# Build
pnpm run build

# Dev server
pnpm run dev
```

Run `pnpm run lint:fix && pnpm run format` after making frontend changes.

### Component Library

Uses **shadcn/ui** components (Radix UI primitives + Tailwind CSS):
- Components location: `frontend/src/components/ui/`
- Add new components: `pnpm dlx shadcn@latest add <component>`
- Follow existing patterns for custom components

### Testing

- Framework: Vitest + React Testing Library
- Run tests: `pnpm run test`
- Test files: `*.test.ts`, `*.test.tsx`

---

## Development Workflow

### Docker (Recommended)

```bash
# Start all services
docker compose up -d

# Seed sample data (creates admin@admin.com / secret123)
make init

# View logs
docker compose logs -f app

# Stop
make stop

# Full teardown
make down
```

### Access Points
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Celery Flower: http://localhost:5555

### Makefile Commands

- `make build` - Build Docker images
- `make run` - Start in detached mode
- `make up` - Start in foreground
- `make watch` - Start with hot-reload
- `make stop` - Stop containers
- `make down` - Remove containers
- `make test` - Run backend tests
- `make migrate` - Apply database migrations
- `make create_migration m="Description"` - Create new migration
- `make downgrade` - Revert last migration
- `make init` - Seed sample data

### Pre-commit Hooks

Pre-commit hooks are configured in `.pre-commit-config.yaml`:
- Ruff linting (auto-fix enabled)
- Ruff formatting
- Type checking (ty)
- Trailing whitespace removal
- End-of-file fixing
- Merge conflict detection

Install hooks: `cd backend && uv run pre-commit install`

---

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push/PR to `backend/` or `frontend/`:

**Backend checks:**
- `uv sync` (dependency installation)
- `uv run ruff check` (linting)
- `uv run ruff format --check` (formatting)
- `uv run ty check` (type checking)

**Frontend checks:**
- `pnpm install` (dependencies)
- `pnpm run build` (build)
- `pnpm run lint` (oxlint)
- `pnpm run format:check` (prettier)

All checks must pass before merging.

---

## Guidelines for AI Agents

1. **Never commit secrets** - Check for .env files, API keys, credentials before commits
2. **Follow existing patterns** - Match the code style of surrounding files
3. **Update documentation** - When adding providers, update `docs/` if applicable
4. **Run quality checks** - Always run lint/format commands after changes
5. **Use type hints** - All Python functions must have type annotations
6. **Test your changes** - Run relevant tests before considering work complete
7. **Provider icons** - When adding providers, include SVG icon in `backend/app/static/provider-icons/`
