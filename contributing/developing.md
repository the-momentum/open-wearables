# Setting Up Your Development Environment

This guide covers setting up your local development environment for Open Wearables.

## Prerequisites

- **Docker** (recommended) - [Install Docker](https://docs.docker.com/get-docker/)
- **uv** - Python package manager ([Install uv](https://docs.astral.sh/uv/)) - manages Python automatically
- **pnpm** - Node.js package manager ([Install pnpm](https://pnpm.io/installation))

For local frontend development without Docker, you'll also need:
- **Node.js 22+** - For frontend development

## Quick Start with Docker (Recommended)

The easiest way to get started is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/the-momentum/open-wearables.git
cd open-wearables

# Start all services with hot-reload (recommended for development)
make watch

# Seed sample data (creates admin@admin.com / secret123)
make init
```

## Access Points

Once running, you can access:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |
| Celery Flower | http://localhost:5555 |

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make build` | Build Docker images |
| `make run` | Start in detached mode |
| `make up` | Start in foreground |
| `make watch` | Start with hot-reload (recommended for development) |
| `make stop` | Stop containers |
| `make down` | Remove containers |
| `make test` | Run backend tests |
| `make migrate` | Apply database migrations |
| `make create_migration m="..."` | Create new migration |
| `make init` | Seed sample data |

## Local Development Without Docker

### Backend Setup

```bash
cd backend

# Create virtual environment and install dependencies
uv sync

# Copy environment file
cp config/.env.example config/.env

# Run database migrations
uv run alembic upgrade head

# Start the backend server (with auto-reload)
uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Copy environment file
cp .env.example .env

# Start development server
pnpm dev
```

## Environment Variables

Copy the example environment files and configure as needed:

- Backend: `backend/config/.env.example` -> `backend/config/.env`
- Frontend: `frontend/.env.example` -> `frontend/.env`

## Development Patterns

For detailed code patterns and architecture guidelines, see:

- [Root AGENTS.md](../AGENTS.md) - General workflow and guidelines
- [Backend AGENTS.md](../backend/AGENTS.md) - Python/FastAPI patterns
- [Frontend AGENTS.md](../frontend/AGENTS.md) - React/TypeScript patterns
