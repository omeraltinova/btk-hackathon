# syntax=docker/dockerfile:1.7

# WHY uv-based image: prebuilt, smaller, and supplies `uv` directly so we don't
# fight with pip/uv install ordering.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# 1) Install deps first for cacheability — only this layer rebuilds when deps change.
COPY pyproject.toml ./
# uv.lock is created on first `uv sync`; copy only if present so initial builds work.
COPY uv.loc[k] ./
RUN printf '# Cüzdan Koçu Backend\n' > /README.md
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

# 2) App source.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

# Reload only useful in dev; docker-compose overrides the command for dev hot-reload.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
