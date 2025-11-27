FROM python:3.13-slim AS builder

    RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
    RUN pip install --no-cache-dir --upgrade pyopenssl

    COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

    WORKDIR /root_project

    COPY uv.lock pyproject.toml ./
    COPY . .

    RUN uv venv /root_project/.venv
    ENV PATH="/root_project/.venv/bin:$PATH"
    RUN uv sync --locked --no-dev

FROM python:3.13-slim

    RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

    WORKDIR /root_project

    COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

    COPY --from=builder /root_project /root_project

    ENV PATH="/root_project/.venv/bin:$PATH"

    # Reinstall to regenerate scripts with correct shebangs for this environment
    RUN uv sync --reinstall

    EXPOSE 8000
