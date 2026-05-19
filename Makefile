# Cüzdan Koçu — top-level convenience targets.
# Use `make help` to discover commands.

.PHONY: help install dev backend frontend lint format type-check test build migrate down clean

help:
	@echo "Cüzdan Koçu — make targets:"
	@echo ""
	@echo "  install        Install backend (uv) and frontend (pnpm) dependencies."
	@echo "  dev            Start the full stack via docker compose (postgres+minio+backend+frontend)."
	@echo "  backend        Start only the FastAPI backend on the host (no Docker)."
	@echo "  frontend       Start only the Next.js dev server on the host (no Docker)."
	@echo "  migrate        Run alembic upgrade head against the configured DATABASE_URL."
	@echo "  lint           Lint backend (ruff) and frontend (eslint, prettier)."
	@echo "  format         Auto-format backend (ruff format) and frontend (prettier)."
	@echo "  type-check     Run mypy --strict on backend and tsc --noEmit on frontend."
	@echo "  test           Run backend pytest suite."
	@echo "  build          Build backend Docker image and frontend production bundle."
	@echo "  down           Stop docker compose stack and remove containers."
	@echo "  clean          Remove caches, .next, .venv, node_modules (use with care)."

install:
	cd backend && uv sync
	cd frontend && pnpm install

dev:
	docker compose up --build

backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && pnpm dev

migrate:
	cd backend && uv run alembic upgrade head

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && pnpm lint && pnpm format:check

format:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm format

type-check:
	cd backend && uv run python -m mypy app
	cd frontend && pnpm type-check

test:
	cd backend && uv run pytest -v

build:
	docker compose build

down:
	docker compose down

clean:
	rm -rf backend/.venv backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache
	rm -rf frontend/.next frontend/node_modules
	@echo "Cleaned. Run 'make install' to restore deps."
