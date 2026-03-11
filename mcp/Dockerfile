FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY app/ app/

# Install the project itself
RUN uv sync --frozen --no-dev

ENV MCP_TRANSPORT=http

EXPOSE 8080

CMD ["uv", "run", "start"]
