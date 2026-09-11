FROM python:3.13-slim AS builder

    COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

    WORKDIR /root_project

    # Install dependencies first (cached unless lock/pyproject change)
    COPY uv.lock pyproject.toml ./
    ENV VIRTUAL_ENV=/opt/venv
    ENV UV_PROJECT_ENVIRONMENT=/opt/venv
    RUN uv venv $VIRTUAL_ENV
    ENV PATH="$VIRTUAL_ENV/bin:$PATH"
    RUN uv sync --locked --no-dev --no-install-project

    # Copy source and install the project itself (fast, deps already cached)
    COPY . .
    RUN uv sync --locked --no-dev --no-editable

FROM python:3.13-slim

    WORKDIR /root_project

    COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

    COPY --from=builder /opt/venv /opt/venv
    COPY --from=builder /root_project /root_project
    ENV VIRTUAL_ENV=/opt/venv
    ENV PATH="/opt/venv/bin:$PATH"
    ENV UV_PROJECT_ENVIRONMENT=/opt/venv
    ENV UV_NO_SYNC=true

    RUN useradd --create-home --shell /usr/sbin/nologin --uid 1000 mcp \
        && chown -R mcp:mcp /opt/venv /root_project
    USER mcp

    EXPOSE 8100

    CMD ["start"]
