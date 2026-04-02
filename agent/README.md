# API

A FastAPI application with PostgreSQL database support, containerized with Docker.

## Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)

## Setup

1. **Create environment file**
   ```bash
   cp ./config/.env.example ./config/.env
   # Edit .env file with your configuration
   ```

## Running the Application

### Docker (Recommended)

```bash
# Start services
docker compose up -d

# Create migration
docker compose exec app uv run alembic revision --autogenerate -m "Description"

# Run migrations
docker compose exec app uv run alembic upgrade head
```

### Local Development

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

### Access the application
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

---

This project was generated from the [Python AI Kit](https://github.com/the-momentum/python-ai-kit).
