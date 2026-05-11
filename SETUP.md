# SETUP.md — Cüzdan Koçu first-time setup

This guide gets you from "freshly cloned repo" to "everything running locally" in ~10 minutes. If anything is unclear, check [`docs/master_plan.md`](docs/master_plan.md) first; if the answer isn't there, ask the team.

## 1. Prerequisites

You need:

| Tool | Version | Verify with |
|------|---------|-------------|
| **Docker Desktop** | 4.30+ (or Docker Engine 27+) | `docker --version` |
| **Docker Compose** | v2 (bundled with modern Docker) | `docker compose version` |
| **Node.js** | 20 LTS or 22 LTS | `node --version` |
| **pnpm** | 11+ | `pnpm --version` |
| **Python** | 3.12.x exactly (not 3.13) | `python --version` |
| **uv** | 0.5+ | `uv --version` |
| **Git** | any modern version | `git --version` |
| **make** | optional but recommended | `make --version` |

If you don't have a tool yet:

- **pnpm:** `npm i -g pnpm` or `corepack enable pnpm`.
- **uv:** `pip install uv` or follow the [official installer](https://docs.astral.sh/uv/getting-started/installation/).
- **make on Windows:** Comes with Git Bash. If missing, install via `choco install make` (chocolatey) or use the equivalent commands from the Makefile.

## 2. Clone & env

```bash
git clone <repo-url> btk-hackathon
cd btk-hackathon
cp .env.example .env
```

Open `.env` and:

- Set `JWT_SECRET` to a strong value: `openssl rand -hex 32`. (The placeholder works for first boot but you must change it before pushing anything to a real environment.)
- `GEMINI_API_KEY` — create one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). You can leave it empty until Day 2; the backend boots without it.
- Leave the `POSTGRES_*`, `MINIO_*`, and `NEXT_PUBLIC_*` defaults as-is for local dev.

## 3. The "everything in Docker" path (recommended for first run)

```bash
docker compose up --build
```

What you should see:

1. `cuzdan-postgres` becomes healthy.
2. `cuzdan-minio` starts (web console at <http://localhost:9001>).
3. `cuzdan-backend` builds, starts uvicorn on port 8000.
4. `cuzdan-frontend` builds and serves on port 3000.

**Verify backend:**

```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0"}
```

**Verify frontend:** open <http://localhost:3000> — the root URL redirects to `/dashboard`. You'll see the sidebar (with the hard-coded demo user "Ayşe Yılmaz" — Day 1 only; replaced by real auth on Day 2) and a "Yakında" placeholder card.

**Verify dark mode:** click the sun/moon icon top-right in the dashboard.

**Run the database migration** (Day 1 ships an initial migration but doesn't auto-apply it — explicit step is safer for hackathon dev):

```bash
docker compose exec backend uv run alembic upgrade head
```

Expected output ends with `Running upgrade -> 0001_initial_schema`. Re-running is a no-op.

To verify the schema exists:

```bash
docker compose exec postgres psql -U cuzdan -d cuzdan -c "\dt"
```

You should see all 8 tables (users, categories, transactions, subscriptions, conversations, messages, agent_memory, proactive_insights) plus `alembic_version`.

To **stop** everything: `docker compose down`. Add `-v` to also wipe the volumes (Postgres data + MinIO data).

## 4. The "fast dev loop" path (run host-side, no Docker for backend/frontend)

For day-to-day development, running backend and frontend directly on the host is significantly faster (hot reload, no rebuilds). Postgres and MinIO still run in Docker.

### 4a. Start only the data services

```bash
docker compose up -d postgres minio
```

### 4b. Backend on the host

```bash
cd backend
uv sync                               # one-time: install deps into ./.venv
uv run alembic upgrade head           # apply migration
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Note:** When running backend on the host, make sure `DATABASE_URL` in `.env` points at `localhost`, not `postgres`. Either edit `.env` or run with `DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan uv run ...`.

### 4c. Frontend on the host

In another terminal:

```bash
cd frontend
pnpm install                          # one-time
pnpm dev
```

Frontend dev server reloads on save and uses the same backend at `NEXT_PUBLIC_API_URL` from `.env`.

## 5. Convenience commands (Makefile)

```bash
make help            # list all targets
make install         # backend uv sync + frontend pnpm install
make dev             # docker compose up (full stack)
make backend         # uvicorn on host
make frontend        # next dev on host
make migrate         # alembic upgrade head
make lint            # ruff + eslint + prettier --check
make format          # auto-fix formatting on both sides
make type-check      # mypy --strict + tsc --noEmit
make test            # pytest
make build           # docker compose build
make down            # stop docker compose
```

## 6. Daily development quality bar

Before pushing a commit:

```bash
make lint && make type-check && make test
```

All three must pass. If `make lint` finds drift, run `make format` first.

## 7. How to verify everything works (full smoke test)

1. `docker compose up --build` (or the host path)
2. `make migrate`
3. `curl http://localhost:8000/health` → 200 OK with JSON
4. Open <http://localhost:8000/docs> → FastAPI Swagger UI shows the (currently empty) routers
5. Open <http://localhost:3000> → redirects to `/dashboard`
6. Click through `/chat`, `/receipts`, `/family` — each shows its placeholder card
7. Open <http://localhost:9001> → MinIO console (login: `minioadmin` / `minioadmin` unless you changed `.env`)
8. Toggle dark mode — body color flips
9. `make test` from repo root → 1 test passes

## 8. Troubleshooting

### `docker compose up` complains about port 5432 / 3000 / 8000 being in use

Another process is bound to that port. Either stop it, or remap the host port in `docker-compose.yml` (e.g. `5433:5432`).

### Backend can't connect to Postgres ("could not translate host name 'postgres' to address")

You're running uvicorn on the host but `DATABASE_URL` still points to the Docker service name. Either:

- run backend in Docker (`docker compose up backend`), or
- change `DATABASE_URL` to `postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan`.

### Alembic migration fails with `function gen_random_uuid() does not exist`

The `pgcrypto` extension wasn't installed. Our `0001_initial_schema.py` runs `CREATE EXTENSION IF NOT EXISTS pgcrypto` first; if you previously partially-applied the migration manually, drop the DB and re-create it:

```bash
docker compose exec postgres psql -U cuzdan -c "DROP DATABASE cuzdan;"
docker compose exec postgres psql -U cuzdan -c "CREATE DATABASE cuzdan;"
make migrate
```

### `pnpm install` complains about ignored builds (sharp / unrs-resolver)

pnpm 11 sandboxes build scripts by default. Approve them once:

```bash
cd frontend
pnpm approve-builds --all
```

(The repo also commits `frontend/pnpm-workspace.yaml` with `allowBuilds`, so this should not happen on a fresh clone.)

### `make` is missing on Windows

Install Git Bash (which bundles `make`), or use the underlying commands directly:

- Lint: `cd backend && uv run ruff check . && uv run ruff format --check . && cd ../frontend && pnpm lint`
- Type-check: `cd backend && uv run mypy app && cd ../frontend && pnpm type-check`

### Frontend build error: "Cannot find package '@eslint/eslintrc'"

`pnpm install` in `frontend/` was incomplete. Re-run:

```bash
cd frontend
pnpm install
```

### CRLF / LF mismatches on Windows

`.gitattributes` in the repo enforces LF for text files. If you committed with CRLF before this was set, run:

```bash
git rm --cached -r .
git reset --hard HEAD
```

### "Hydration mismatch" warning in the browser

`next-themes` adds the `class="dark"` attribute on `<html>` after mount; the root layout uses `suppressHydrationWarning` for this exact reason. If you see other hydration warnings, check that you're not reading `localStorage` / `Date.now()` outside a `useEffect`.

## 9. What changes day-by-day

See [`TEAM_PROTOCOL.md`](TEAM_PROTOCOL.md) for the numbered task list and owners, and [`WORKDIVISION.md`](WORKDIVISION.md) for the collaboration rules around dependencies, review, and handoff. As features land, this SETUP.md should stay accurate — if a step here breaks, fix it in the same PR that introduced the regression.
