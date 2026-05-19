# SETUP.md — Cüzdan Koçu first-time setup

This guide gets you from "freshly cloned repo" to "everything running locally" in ~10 minutes. If anything is unclear, check [`docs/master_plan.md`](docs/master_plan.md) first; if the answer isn't there, ask the team.

## 1. Prerequisites

You need:

| Tool | Version | Verify with |
|------|---------|-------------|
| **Docker Desktop** | 4.30+ (or Docker Engine 27+) | `docker --version` |
| **Docker Compose** | v2 (bundled with modern Docker) | `docker compose version` |
| **Node.js** | 22.13+ | `node --version` |
| **pnpm** | 11+ | `pnpm --version` |
| **Python** | 3.12.x exactly (not 3.13) | `python --version` |
| **uv** | 0.5+ | `uv --version` |
| **Git** | any modern version | `git --version` |
| **make** | optional but recommended | `make --version` |

If you don't have a tool yet:

- **pnpm:** `npm i -g pnpm` or `corepack enable pnpm`. pnpm 11 requires Node 22.13+.
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
- Set `NEXTAUTH_SECRET` to a strong value too; it can use the same generation command as `JWT_SECRET` but should be a separate value outside local demos.
- `LLM_PROVIDER` — keep `gemini` for direct Google AI Studio, or set `openrouter` to route chat models through OpenRouter.
- `GEMINI_API_KEY` — create one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Required for the live LangGraph LLM path when `LLM_PROVIDER=gemini`.
- `GEMINI_IMAGE_MODEL`, `GEMINI_LIVE_MODEL`, `GEMINI_LIVE_VOICE`, `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE`, and `MINIO_BUCKET_ILLUSTRATIONS` — defaults work locally; concept illustration, direct Gemini audio understanding for microphone transcription, Gemini Live voice chat, and provider-backed message read-aloud in chat use the same Gemini key.
- `OPENROUTER_API_KEY` — create one at [openrouter.ai/keys](https://openrouter.ai/keys). Required for the live LangGraph LLM path when `LLM_PROVIDER=openrouter`; default chat model is `google/gemini-3.1-flash-lite`, default image model is `google/gemini-3.1-flash-image-preview`, default STT model is `google/chirp-3`, and default TTS model is `google/gemini-3.1-flash-tts-preview`.
- If the selected LLM key is missing, `/api/chat/stream` still works through the deterministic scoped fallback and streams a Turkish setup notice. Live LLM wording, child-coach natural language, and image OCR require a configured Gemini/OpenRouter key.
- Real image OCR on the `/transactions` receipt scanner and chat receipt attachments uses the same provider choice. Without a configured provider key, real image OCR returns a Turkish "service not ready" error.
- Direct Gemini microphone transcription can normalize unsupported browser recordings with `ffmpeg`. Docker images include it; if you run the backend directly on the host and use `LLM_PROVIDER=gemini`, install `ffmpeg` locally as well.
- Leave the `POSTGRES_*`, `MINIO_*`, `ILLUSTRATION_DAILY_LIMIT`, and `NEXT_PUBLIC_*` defaults as-is for local dev.

## 3. The "everything in Docker" path (recommended for first run)

```bash
docker compose up --build
```

Keep this terminal open. Run migration, seed, and smoke-test commands from a second terminal.

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

**Verify frontend:** open <http://localhost:3000> — unauthenticated users are redirected to `/login`. Register or log in, then `/dashboard`, `/transactions`, `/income-expense`, `/goals`, `/learn`, `/chat`, `/family`, and `/account` render inside the authenticated app shell. `/transactions` contains the receipt OCR flow; the old `/receipts` URL redirects there. `/family` can create child profiles and switch dashboard/chat calls into that child context.

**Verify dark mode:** click the sun/moon icon top-right in the dashboard.

**Run the database migration** from a second terminal:

```bash
docker compose exec backend uv run alembic upgrade head
```

Expected output applies all pending Alembic revisions through the current `head`. Re-running is a no-op.

To verify the schema exists:

```bash
docker compose exec postgres psql -U cuzdan -d cuzdan -c "\dt"
```

You should see the application tables, including users, categories, transactions, subscriptions, conversations, messages, agent_memory, proactive_insights, saving_goals, generated_reports, plus `alembic_version`.

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
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan \
MINIO_ENDPOINT=localhost:9000 \
uv run alembic upgrade head           # apply migration
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan \
MINIO_ENDPOINT=localhost:9000 \
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Note:** When running backend on the host, `DATABASE_URL` must point at `localhost`, not Docker's `postgres` service name. `MINIO_ENDPOINT` must also be `localhost:9000`, not Docker's `minio:9000` service name. You can either use the inline overrides above or edit your local `.env` for host-side development.

### 4c. Frontend on the host

In another terminal:

```bash
cd frontend
pnpm install                          # one-time
pnpm dev
```

Frontend dev server reloads on save and uses `NEXT_PUBLIC_API_URL` for browser calls. NextAuth credential login runs server-side; on the host it falls back to `http://localhost:8000`, while Docker Compose passes `NEXT_PRIVATE_API_URL=http://backend:8000`.

## 5. Convenience commands (Makefile)

```bash
make help            # list all targets
make install         # backend uv sync + frontend pnpm install
make dev             # docker compose up (full stack)
make backend         # uvicorn on host
make frontend        # next dev on host
make migrate         # alembic upgrade head against the configured DATABASE_URL
make lint            # ruff + eslint + prettier --check
make format          # auto-fix formatting on both sides
make type-check      # mypy --strict + tsc --noEmit
make test            # pytest
make build           # docker compose build
make down            # stop docker compose
```

`make backend` and `make migrate` run on the host. If your `.env` still uses Docker service names such as `postgres` and `minio`, either use the explicit host commands in section 4b or prefer the Docker-safe migration command: `docker compose exec backend uv run alembic upgrade head`.

## 6. Demo family and proactive worker

After migrations, you can seed the local Yılmaz demo family:

Docker path:

```bash
docker compose exec backend uv run python -m app.workers.demo_seed
```

Host path:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan \
MINIO_ENDPOINT=localhost:9000 \
uv run python ../seeds/demo_family.py
```

The script creates/updates `is_demo=true` Ayşe and Mehmet parent demo accounts; Elif, Deniz, and Zeynep as child demo profiles; Kerem as an individual demo user; sample scoped transactions, goals, categories, envelopes, recurring records, and proactive demo data.

```text
ayse@demo.cuzdan-kocu.app / demo123
mehmet@demo.cuzdan-kocu.app / demo123
elif@demo.cuzdan-kocu.app / demo123
deniz@demo.cuzdan-kocu.app / demo123
zeynep@demo.cuzdan-kocu.app / demo123
kerem@demo.cuzdan-kocu.app / demo123
```

To refresh proactive insights manually for all non-child users:

Docker path:

```bash
docker compose exec backend uv run python -m app.workers.proactive
```

Host path:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan \
MINIO_ENDPOINT=localhost:9000 \
uv run python -m app.workers.proactive
```

For production, wire the same command to cron/platform scheduler after deploy, or call `POST /api/insights/refresh` from an authenticated session when a single user's dashboard needs an immediate refresh.

## 7. Daily development quality bar

Before pushing a commit:

```bash
make lint && make type-check && make test
```

All three must pass. If `make lint` finds drift, run `make format` first.

## 8. How to verify everything works (full smoke test)

1. `docker compose up --build` (or the host path)
2. `docker compose exec backend uv run alembic upgrade head`
3. `docker compose exec backend uv run python -m app.workers.demo_seed`
4. `curl http://localhost:8000/health` → 200 OK with JSON
5. Open <http://localhost:8000/docs> → FastAPI Swagger UI shows the implemented auth, transactions, subscriptions, receipts, chat, family, insights, reports, STT/TTS, voice, export, memory, and goal routers.
6. Open <http://localhost:3000> → unauthenticated users land on `/login`; after login the app opens the authenticated shell.
7. Click through `/dashboard`, `/transactions`, `/income-expense`, `/goals`, `/learn`, `/chat`, `/family`, `/account`.
8. On `/transactions`, open `Fiş tara`, upload a JPG/PNG/WEBP receipt under 5 MB, review the OCR preview, and confirm a transaction.
9. Create a child profile on `/family`, switch into it, then open `/dashboard` and `/chat`. The active child banner should be visible and API calls should use the child context.
10. With `GEMINI_API_KEY` or `OPENROUTER_API_KEY` configured, ask chat a finance question, confirm the stream uses the live LangGraph route, press the microphone button, stop after speaking, and confirm the transcript is sent as a chat message. Then click the speaker icon on the reply and confirm provider-backed Turkish audio plays. Also press the headphones button beside the microphone: in Gemini mode confirm Live API voice chat opens; in OpenRouter mode confirm the persistent cascade loop runs STT → chat/LLM → TTS. Without a working voice provider, confirm browser speech fallback keeps the flow usable.
11. Attach a receipt image in `/chat`, then verify an `analyze_receipt` tool trace appears. Confirmed transaction saving still happens through `/transactions` edit-before-save flow.
12. Ask chat for a monthly coach report and confirm the DOCX download card appears; download should go through `/api/reports/{report_id}/download`.
13. Open `/dashboard`; the insight banner should load from `/api/insights`. Click refresh to trigger `POST /api/insights/refresh`.
14. Open <http://localhost:9001> → MinIO console (login: `minioadmin` / `minioadmin` unless you changed `.env`)
15. Toggle dark mode — body color flips
16. `make test` from repo root → backend pytest suite passes

## 9. Troubleshooting

### `docker compose up` complains about port 5432 / 3000 / 8000 being in use

Another process is bound to that port. Either stop it, or remap the host port in `docker-compose.yml` (e.g. `5433:5432`).

### Backend can't connect to Postgres ("could not translate host name 'postgres' to address")

You're running uvicorn on the host but `DATABASE_URL` still points to the Docker service name. Either:

- run backend in Docker (`docker compose up backend`), or
- change `DATABASE_URL` to `postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan`.

### Alembic migration fails with `function gen_random_uuid() does not exist`

The `pgcrypto` extension should be installed by the first migration. If this happened after a partially-applied manual migration on a disposable local database, reset the local volumes and migrate again:

```bash
docker compose down -v
docker compose up -d --build
docker compose exec backend uv run alembic upgrade head
```

Only use `down -v` when you are okay with deleting local Postgres and MinIO data.

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
- Type-check: `cd backend && uv run python -m mypy app && cd ../frontend && pnpm type-check`

### Frontend build error: "Cannot find package '@eslint/eslintrc'"

`pnpm install` in `frontend/` was incomplete. Re-run:

```bash
cd frontend
pnpm install
```

### CRLF / LF mismatches on Windows

`.gitattributes` in the repo enforces LF for text files. If your editor keeps changing line endings, set it to LF and then check what changed:

```bash
git status --short
git diff --check
```

Do not discard changes until you confirm they are only line-ending noise.

### "Hydration mismatch" warning in the browser

`next-themes` adds the `class="dark"` attribute on `<html>` after mount; the root layout uses `suppressHydrationWarning` for this exact reason. If you see other hydration warnings, check that you're not reading `localStorage` / `Date.now()` outside a `useEffect`.

## 10. Project workflow notes

See [`TEAM_PROTOCOL.md`](TEAM_PROTOCOL.md) for the numbered task list and owners, and [`WORKDIVISION.md`](WORKDIVISION.md) for the collaboration rules around dependencies, review, and handoff. As features land, this SETUP.md should stay accurate — if a step here breaks, fix it in the same PR that introduced the regression.
