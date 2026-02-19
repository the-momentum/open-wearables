# Backend

FastAPI backend for the Open Wearables platform.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- PostgreSQL database

## Development

### Virtual Environment Setup

The project uses a virtual environment (`.venv`) located in the `backend/` directory.

**First-time setup:**

Proceed to the `backend` directory:
```bash
cd backend
```

and run:

```bash
uv sync
```

This will:
- Create the `.venv` directory in `backend/`
- Install all project dependencies
- Set up the virtual environment that VS Code will automatically use

**VS Code Configuration:**
- The workspace is configured to use `backend/.venv/bin/python` as the default interpreter (see `.vscode/settings.json`)
- After running `uv sync`, VS Code should automatically detect and use the virtual environment
- If it doesn't, reload the VS Code window or manually select the interpreter from the command palette (Cmd+Shift+P → "Python: Select Interpreter")

**Recreating the virtual environment:**
If you need to recreate the virtual environment:
```bash
rm -rf .venv  # Optional: remove existing venv
uv sync       # Recreate and install dependencies
```

**Note:** The `.venv` directory is already in `.gitignore`, so you don't need to worry about committing it.

### Installing Dependencies

```bash
# Install all dependencies (including dev dependencies)
uv sync

# Install only production dependencies
uv sync --no-dev

# Install with code quality tools
uv sync --group code-quality
```

### Running the Application

**Using Docker (Recommended):**

```bash
# From the project root directory
# Start services
docker compose up -d

# Run migrations
docker compose exec app uv run alembic upgrade head
```

The API will be available at:
- 🌐 API: http://localhost:8000
- 📚 Swagger: http://localhost:8000/docs

**Local Development:**

```bash
# Install dependencies
uv sync

# Start PostgreSQL locally

# Create migration
uv run alembic revision --autogenerate -m "Description"

# Run migrations
uv run alembic upgrade head

# Start development server
uv run fastapi run app/main.py --reload
```

### Database Migrations

**Create a new migration:**
```bash
# Using Docker
docker compose exec app uv run alembic revision --autogenerate -m "Description of changes"

# Local development
uv run alembic revision --autogenerate -m "Description of changes"
```

**Run migrations:**
```bash
# Using Docker
docker compose exec app uv run alembic upgrade head

# Local development
uv run alembic upgrade head
```

**Rollback migrations:**
```bash
# Using Docker
docker compose exec app uv run alembic downgrade -1

# Local development
uv run alembic downgrade -1
```

### Running Tests

Tests use **testcontainers** — a disposable PostgreSQL container is created
automatically. Just make sure Docker is running.

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/api/v1/test_users.py
```

### Code Quality

The project uses [Ruff](https://github.com/astral-sh/ruff) for linting and formatting.

**Check code quality:**
```bash
uv run ruff check .
uv run ruff format . --check
```

**Fix issues automatically:**
```bash
uv run ruff check . --fix
uv run ruff format .
```

**Pre-commit hooks:**
```bash
# Install pre-commit hooks
uv run pre-commit install

# Run hooks manually
uv run pre-commit run --all-files
```

## Project Structure

```
backend/
├── app/                    # Main application code
│   ├── api/               # API routes
│   │   └── routes/        # Route handlers organized by version
│   ├── config.py          # Configuration settings
│   ├── database.py        # Database connection and session management
│   ├── main.py            # FastAPI application entry point
│   ├── models/            # SQLAlchemy database models
│   ├── repositories/      # Data access layer
│   ├── schemas/           # Pydantic schemas for request/response validation
│   ├── services/          # Business logic layer
│   └── utils/             # Utility functions
├── migrations/            # Alembic database migrations
├── scripts/               # Utility scripts
├── alembic.ini            # Alembic configuration
├── pyproject.toml         # Project dependencies and configuration
└── uv.lock                # Locked dependency versions
```

## Environment Variables

Create a `.env` file in the `config/` directory (see `config/.env.example` for reference). Required environment variables include:

- Database connection settings
- OAuth provider credentials
- JWT secrets
- Other service configurations

## Additional Services

The backend also includes:

- **Celery**: For background task processing
- **Flower**: Celery monitoring (available at http://localhost:5555 when running)
