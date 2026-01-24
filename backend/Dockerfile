FROM python:3.13-slim AS builder

    RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
    RUN pip install --no-cache-dir --upgrade pip pyopenssl uv

    WORKDIR /root_project

    COPY uv.lock pyproject.toml ./
    COPY . .

    ENV VIRTUAL_ENV=/opt/venv
    RUN uv venv $VIRTUAL_ENV
    ENV PATH="$VIRTUAL_ENV/bin:$PATH"
    RUN uv sync --locked --no-dev

FROM python:3.13-slim

    RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
    RUN pip install --no-cache-dir uv

    WORKDIR /root_project

    COPY --from=builder /opt/venv /opt/venv
    COPY --from=builder /root_project /root_project
    ENV VIRTUAL_ENV=/opt/venv
    ENV PATH="/opt/venv/bin:$PATH"
    ENV UV_PROJECT_ENVIRONMENT=/opt/venv

    EXPOSE 8000
