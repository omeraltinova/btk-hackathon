# `decisions.md` — Operational journal for coding agents

> **Purpose.** This is a chronological log of **operational learnings, tool quirks, non-obvious decisions, and lessons** discovered while building Cüzdan Koçu. It is the companion of [`master_plan.md`](master_plan.md), not a replacement.
>
> - **`master_plan.md`** = the constitution: vision, scope, schema, day-by-day plan. High-stability. Updated only when something *architectural* changes; bump the version number.
> - **`decisions.md`** (this file) = the engineering journal: things the next agent or next teammate should know but that don't belong in the constitution. Low-stability, append-only.

## How to use this file (agent instruction)

Whenever you finish a meaningful chunk of work (a day, a feature, a bug fix, a deploy), and you discover:

- A tool quirk or version-specific gotcha (e.g. "pnpm 11 sandboxes build scripts by default")
- A non-obvious trade-off you made (e.g. "chose sync SQLAlchemy because…")
- A workaround for a library bug
- A pattern you adopted that future code should mirror
- A pattern you abandoned and *why*
- A security or supply-chain note (CVE bump, dependency replacement)
- An open question whose answer will matter next session

…**append a new entry to this file**. Don't edit older entries (history matters); add new ones at the bottom of the relevant section.

Each entry follows the format below. Keep it short — one paragraph is usually enough.

```md
### YYYY-MM-DD — Day N — Short title

**Context:** What you were doing.
**Decision/learning:** What you discovered or chose.
**Why it matters:** What the next agent or human needs to do (or NOT do) because of this.
**Reference:** Master plan section, file path, or external link if useful.
```

If a learning is large enough to be architectural (schema change, scope change, day-plan revision), **also** update `master_plan.md` and bump its version. Mention the bump in your entry here.

---

## Log

## Day 1 — 11 May 2026 — Bootstrap

### 2026-05-11 — Day 1 — Master plan bumped to v0.3

**Context:** Day 1 bootstrap. Several Day 1 decisions had architectural implications.
**Decision/learning:** Updated `master_plan.md` from v0.2 to v0.3 with auth method (email+password, not magic link), `users.password_hash` column, `updated_at` standard column on every table, pnpm + uv package manager declaration, and a new coding rule 11. See the "v0.3 değişiklikleri" line at the bottom of `master_plan.md`.
**Why it matters:** If a future decision contradicts the plan, **stop and bump the plan first** (operating rule §27.7). Do not let code drift from the plan silently.
**Reference:** `docs/master_plan.md` v0.3 footer.

### 2026-05-11 — Day 1 — Schema: every table has `created_at` + `updated_at`

**Context:** Master plan §15 v0.2 only had `created_at` on most tables and only `updated_at` on `agent_memory`.
**Decision/learning:** Standardised every table with both columns via `TimestampMixin` in `backend/app/models/base.py`. SQLAlchemy `onupdate=func.now()` keeps `updated_at` accurate for ORM updates; the DB-level `server_default=func.now()` covers raw SQL paths and Alembic backfills.
**Why it matters:** Every new model must inherit `TimestampMixin`. Don't redeclare `created_at`/`updated_at` on subclasses. Coding rule 11 in `master_plan.md` §27 enforces this.
**Reference:** `backend/app/models/base.py`, `master_plan.md` §15 v0.3 note.

### 2026-05-11 — Day 1 — `password_hash` is nullable

**Context:** Master plan v0.3 specifies email+password for parent/individual, but child accounts log in via parent's family switch (Day 5) and have no password of their own.
**Decision/learning:** `users.password_hash` is `TEXT NULL`. NULL is enforced application-side: the auth router (Day 2) must reject login attempts where `password_hash IS NULL`. There is no DB-level CHECK because `role='child' AND password_hash IS NULL` is a legitimate state.
**Why it matters:** Day 2 `/api/auth/login` MUST short-circuit before bcrypt verify when `password_hash` is NULL, otherwise passlib will raise. Day 5 family-switch endpoint issues a new JWT for the child without ever touching the password field.
**Reference:** `backend/app/models/user.py` docstring, `master_plan.md` §15 v0.3 note.

### 2026-05-11 — Day 1 — `categories.user_id` NULL means "system default"

**Context:** Master plan §15 made `categories.user_id` nullable; Day 1 brief S3 explicitly confirmed that NULL means system-default category, user-owned overrides have `user_id = <user>`.
**Decision/learning:** Application reads must use `WHERE user_id = :current_user OR user_id IS NULL`. Never query categories with `WHERE user_id = :current_user` alone, or system defaults disappear.
**Why it matters:** Day 3 `get_spending` tool and the dashboard category aggregation must include system defaults. The Day 5 demo seeder will create a few system-default categories (`user_id=NULL`) and let user overrides shadow them by name.
**Reference:** `backend/app/models/category.py`, `master_plan.md` §15.

### 2026-05-11 — Day 1 — Constraint naming: short suffix to avoid double prefix

**Context:** `Base.metadata` uses a SQLAlchemy `naming_convention` that prepends `ck_<table>_` to check constraints. If the constraint `name` parameter also contains the table name, the result is `ck_users_users_role_check` (and worse, gets truncated past 63 chars).
**Decision/learning:** Use a short suffix like `name="role_valid"`; the convention turns it into `ck_users_role_valid` cleanly.
**Why it matters:** Future migrations that reference constraints by name (e.g. `op.drop_constraint`) must use the **convention-prefixed** name (`ck_users_role_valid`), not the bare suffix.
**Reference:** `backend/app/models/base.py` (NAMING_CONVENTION), `backend/alembic/versions/0001_initial_schema.py`.

### 2026-05-11 — Day 1 — pgcrypto extension in the migration, not in setup

**Context:** `gen_random_uuid()` is in `pgcrypto`. Coolify-managed Postgres images may or may not ship it pre-installed.
**Decision/learning:** The first migration explicitly runs `CREATE EXTENSION IF NOT EXISTS pgcrypto` (and `DROP EXTENSION IF EXISTS pgcrypto` in `downgrade`). No manual DB setup step required for any environment.
**Why it matters:** Don't add `CREATE EXTENSION` to seed scripts or backend startup; it belongs in the migration so the schema is portable.
**Reference:** `backend/alembic/versions/0001_initial_schema.py` lines around `upgrade()` top and `downgrade()` bottom.

### 2026-05-11 — Day 1 — pnpm 11 sandboxes build scripts (`pnpm-workspace.yaml.allowBuilds`)

**Context:** Fresh `pnpm install` failed with `ERR_PNPM_IGNORED_BUILDS: sharp@0.33.5, unrs-resolver@1.11.1`. pnpm 11 changed the default — postinstall scripts of native deps are blocked unless explicitly allowed.
**Decision/learning:** We committed `frontend/pnpm-workspace.yaml` with:

```yaml
allowBuilds:
  sharp: true
  unrs-resolver: true
```

This file is auto-generated by `pnpm approve-builds --all`. We also kept the legacy `pnpm.onlyBuiltDependencies` field in `package.json` for pnpm 9/10 compatibility.
**Why it matters:** If a new native dep is added (e.g. `bcrypt-native` Day 2), `pnpm install` will block its postinstall and the build will fail in a confusing way. Workaround: run `pnpm approve-builds --all` once locally; commit the updated `pnpm-workspace.yaml`. Document the package's name in `SETUP.md` troubleshooting section.

### 2026-05-11 — Day 1 — Next.js bumped 15.0.4 → 15.5.18 (CVE-2025-66478)

**Context:** Initial `package.json` pinned `next@15.0.4`. pnpm install warned: "deprecated next@15.0.4: This version has a security vulnerability."
**Decision/learning:** Bumped to `next@15.5.18` and `eslint-config-next@15.5.18` (latest patched 15.x). Master plan §13 says "15.x" so still in spec.
**Why it matters:** Pin to the latest patched minor. **Don't downgrade Next.js.** If you bump to 16.x, that's a major architectural change — update master plan first.
**Reference:** <https://nextjs.org/blog/CVE-2025-66478>

### 2026-05-11 — Day 1 — `react/no-unescaped-entities` disabled for Turkish text

**Context:** ESLint rule errors out on `'` in JSX text content, demanding `&apos;` or `&rsquo;`. Turkish uses apostrophes constantly ("Cüzdan Koçu'na", "Day 2'de"); React renders them correctly without escaping.
**Decision/learning:** Rule disabled in `frontend/eslint.config.mjs` with an inline comment explaining the trade-off.
**Why it matters:** Don't re-enable this rule unless you also have a tooling pass that auto-escapes Turkish apostrophes. The risk is purely cosmetic; React's text rendering is safe.

### 2026-05-11 — Day 1 — `next lint` deprecated, switched to `eslint .`

**Context:** `next lint` prints a deprecation warning starting in Next.js 15.x and is removed in 16. Also: it emits "Next.js plugin was not detected" warnings with our flat config because it doesn't fully understand FlatCompat shim.
**Decision/learning:** `frontend/package.json` script `"lint": "eslint ."`. ESLint flat config loads `next/core-web-vitals` via `FlatCompat` from `@eslint/eslintrc`.
**Why it matters:** When bumping to Next.js 16 (post-hackathon), this script keeps working. If you ever migrate to a fully-native flat config (no `FlatCompat`), update `eslint.config.mjs` and remove the `@eslint/eslintrc` dependency.

### 2026-05-11 — Day 1 — Sync SQLAlchemy engine (not async)

**Context:** FastAPI supports both, and LangGraph examples lean async.
**Decision/learning:** Picked sync engine + sync `Session` in `backend/app/db.py`. FastAPI runs sync DB calls in a worker thread; LangGraph tools that need DB will use the same `get_db` pattern.
**Why it matters:** When implementing agent tools (Day 3+), call DB synchronously inside the tool function. Don't try to `await` SQLAlchemy queries — you'll hit "AsyncSession needs sqlalchemy.ext.asyncio" confusion. If we ever migrate to async, every tool signature changes; not in scope for the hackathon.
**Reference:** `backend/app/db.py` top docstring.

### 2026-05-11 — Day 1 — Hand-written migration, not autogenerated

**Context:** Alembic autogenerate doesn't pick up everything we need: partial indexes (`WHERE is_dismissed = FALSE` on `proactive_insights`), the `pgcrypto` extension creation, or our preferred constraint names.
**Decision/learning:** `backend/alembic/versions/0001_initial_schema.py` is hand-written and matches `master_plan.md` §15 exactly. Future migrations should still use `alembic revision --autogenerate` as a *starting point* — then hand-edit before committing.
**Why it matters:** Day 2+ migrations: always read the autogenerated diff before merging. Pay extra attention to partial indexes, server_defaults, and check constraint names — autogenerate often gets these wrong or drops them entirely.

### 2026-05-11 — Day 1 — JWT payload is `dict[str, Any]`, not the `TokenPayload` TypedDict

**Context:** PyJWT's `jwt.encode` signature wants `dict[str, Any]`, not a TypedDict — mypy errors with invariance: "Argument 1 has incompatible type 'TokenPayload'; expected 'dict[str, Any]'".
**Decision/learning:** In `create_token`, the local payload is typed `dict[str, Any]` and the `TokenPayload` TypedDict is used only as the return type of `verify_token` (where we re-validate the shape). Comment in `auth.py` explains the reason.
**Why it matters:** Don't try to "tighten" the type back to `TokenPayload` in `create_token` — mypy will reject it. If PyJWT ever ships proper generic types, revisit.
**Reference:** `backend/app/auth.py` `create_token`.

### 2026-05-11 — Day 1 — Hard-coded demo user in sidebar (Day 1 ONLY)

**Context:** Brief required a sidebar with user chip and nav, but the auth UI lands Day 2 — there's no real user object yet.
**Decision/learning:** `HARDCODED_DEMO_USER = { name: "Ayşe Yılmaz", family: "Yılmaz", role: "parent", … }` in `frontend/components/sidebar.tsx`, marked with `// TODO Day 2: replace with auth context`.
**Why it matters:** Day 2 must remove this constant and wire the user from the React `AuthContext` (or NextAuth session if that path wins — see open question Q1 below). **Grep for `HARDCODED_DEMO_USER` before merging Day 2 — there should be zero references when Day 2 ends.**

### 2026-05-11 — Day 1 — `.env` file location for backend (two paths)

**Context:** When running backend via Docker Compose, the working directory is `/app` and `.env` is at the repo root (mounted via env_file). When running uvicorn directly on the host from `backend/`, `.env` is one level up.
**Decision/learning:** `backend/app/config.py` `SettingsConfigDict` declares `env_file=("../.env", ".env")` — pydantic-settings checks both locations.
**Why it matters:** Both run modes "just work". If a teammate creates a `backend/.env` it will silently shadow the root `.env` — call this out in code review.
**Reference:** `backend/app/config.py`.

### 2026-05-11 — Day 1 — Open question Q1: do we keep NextAuth.js?

**Context:** Master plan §13 still lists "NextAuth.js sadece frontend session taşıyıcı" but with email+password+JWT, NextAuth adds little value over a tiny React `AuthContext` + `localStorage` token via `lib/api.ts`.
**Status:** Awaiting team decision. If we drop NextAuth, update master plan §13 and §27, and adjust Day 2 plan in `WORKDIVISION.md`.
**Why it matters:** Day 2 begins the auth UI; the decision changes which files are touched.

### 2026-05-11 — Day 1 — Open question Q2: `NEXT_PUBLIC_API_URL` from inside Docker

**Context:** From the browser, `http://localhost:8000` is correct. From a Server Component running inside the frontend container, `localhost:8000` is the container's localhost — wrong; need `http://backend:8000`.
**Status:** Day 1 doesn't do any Server-Component-to-backend calls; the question becomes real on Day 3 dashboard if we go SSR.
**Why it matters:** When the first SSR data fetch lands, add a `NEXT_PRIVATE_API_URL` (or split the env variable) and route Server Components through the Docker service name.

### 2026-05-11 — Day 1 — Verification limits on Day 1 bootstrap machine

**Context:** Day 1 bootstrap was done on a Windows machine without Docker Desktop installed. Could not run `docker compose up --build` or `alembic upgrade head` against a real Postgres.
**What WAS verified locally:**

- `uv sync` + `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q` all green
- `pnpm install && pnpm lint && pnpm type-check && pnpm format:check && pnpm build` all green
- `uvicorn` ran host-side, `GET /health` returned `{"status":"ok","version":"0.1.0"}`
- `pnpm dev` ran host-side, all 6 routes (`/`, `/dashboard`, `/chat`, `/receipts`, `/family`, `/login`) returned 200 with expected Turkish content
- `uv run alembic upgrade base:head --sql` produced 9 CREATE TABLEs (8 schema tables + alembic_version) with correct partial index, pgcrypto extension, and FK CASCADE wiring — inspected manually

**What was NOT verified locally and MUST be confirmed on a Docker-capable machine:**

- `docker compose up --build` brings all four services up green
- `make migrate` (i.e. `alembic upgrade head` against real Postgres) applies cleanly
- The full `alembic upgrade head && alembic downgrade base && alembic upgrade head` round-trip

**Why it matters:** Day 2 cannot begin until these three are confirmed on a real Docker host. See `SETUP.md` §7 for the exact verification recipe.

### 2026-05-11 — Day 1 — Commit rules documented in AGENTS.md

**Context:** Team wanted agents to follow a consistent commit format instead of ad-hoc messages.
**Decision/learning:** Added an English "Commit rules" section to `AGENTS.md`: Conventional Commits, English type/scope/subject, separated scopes, verification in the body, no secrets or ignored artifacts, and `git status --short` before committing.
**Why it matters:** Future agents should stage files intentionally and make reviewable commits that preserve the backend/frontend/docs/infrastructure boundaries.
**Reference:** `AGENTS.md` commit rules section.

### 2026-05-11 — Day 1 — Frontend design context and motion baseline

**Context:** Day 1 frontend was upgraded from plain placeholders to a more distinctive app preview while keeping routers/pages static until their planned implementation days.
**Decision/learning:** Added `.impeccable.md` with reusable design context, switched the frontend theme to OKLCH tokens, paired Afacad + Commissioner via `next/font`, and added CSS-only page/micro motion with `prefers-reduced-motion` support. The app shell is now mobile-first with horizontal nav on small screens and richer static previews for dashboard/chat/receipts/family/login.
**Why it matters:** Future UI work should preserve the warm, practical, non-judgmental family-finance direction and reuse the OKLCH/Tailwind tokens instead of reintroducing generic slate shadcn defaults. Day 2 auth work still needs to replace the hard-coded sidebar user.
**Reference:** `.impeccable.md`, `frontend/app/globals.css`, `frontend/tailwind.config.ts`, `frontend/app/(app)/*/page.tsx`.

### 2026-05-11 — Day 1 — Ledger visual language replaces generic dashboard look

**Context:** Follow-up critique: the first design pass still looked too AI-like because it relied on glow blobs, rounded card grids, and repeated hero/stat compositions.
**Decision/learning:** Reworked the frontend around a household-ledger metaphor: ruled notebook sheets, receipt-tape panels, cash-envelope summary blocks, stamped labels, binder holes, and tab-shaped navigation. Removed most page-level shadcn card usage from the static preview pages; kept components available for later functional forms/dialogs.
**Why it matters:** Future pages should extend the ledger/receipt/envelope primitives instead of falling back to generic SaaS cards. If new features need containers, prefer semantic financial metaphors (defter sayfası, fiş, zarf, kaşe) before adding another rounded panel.
**Reference:** `.impeccable.md`, `frontend/app/globals.css`, `frontend/components/sidebar.tsx`, `frontend/app/(app)/dashboard/page.tsx`.

### 2026-05-11 — Day 1 — NextAuth decision resolved

**Context:** Open question Q1 asked whether to keep NextAuth.js as the frontend session carrier or replace it with a tiny AuthContext/localStorage approach.
**Decision/learning:** Team chose to keep NextAuth. This matches `master_plan.md` §13, so no master-plan bump is required. Updated `WORKDIVISION.md` Day 2 frontend file map to use a Credentials provider in `frontend/app/api/auth/[...nextauth]/route.ts`, shared config in `frontend/lib/auth.ts`, and `signIn("credentials")` from the login page.
**Why it matters:** Day 2 frontend should store the FastAPI JWT inside NextAuth JWT/session callbacks and pass that backend token to `lib/api.ts`. Do not introduce a competing AuthContext unless the plan is changed first.
**Reference:** `docs/master_plan.md` §13, `WORKDIVISION.md` Day 2 Person B.

### 2026-05-11 — Day 1 — Initial migration constraint names corrected

**Context:** Offline Alembic SQL showed double-prefixed check constraints like `ck_users_ck_users_role_valid`, even though the Day 1 naming decision requires short suffixes.
**Decision/learning:** Changed check constraint names in `backend/alembic/versions/0001_initial_schema.py` to suffixes (`role_valid`, `source_valid`, etc.) so SQLAlchemy's naming convention emits clean names like `ck_users_role_valid`.
**Why it matters:** Run the real first migration only after this fix is present. If a database was already migrated with the old double-prefixed names, drop/recreate the dev DB before continuing Day 2.
**Reference:** `backend/alembic/versions/0001_initial_schema.py`, Day 1 constraint naming entry above.

### 2026-05-11 — Day 1 — Docker Compose secret-scanner false positive reduced

**Context:** GitGuardian flagged the Compose-built `DATABASE_URL` because it contained local fallback credentials like `cuzdan:cuzdan`.
**Decision/learning:** Removed hardcoded credential fallbacks from `docker-compose.yml` for Postgres, MinIO, and `JWT_SECRET`. Compose now requires values from `.env` and fails with an explicit "copy .env.example to .env" message when they are missing. The Postgres healthcheck uses container environment variables (`$${POSTGRES_USER}`) instead of host-side interpolation.
**Why it matters:** Normal local Docker setup still works after `cp .env.example .env`, but running Compose without `.env` now fails early rather than silently using placeholder secrets. Real production values must still live outside Git.
**Reference:** `docker-compose.yml`, `SETUP.md` §2.

### 2026-05-11 — Day 1 — Work split changed from people to responsibility lanes

**Context:** The active plan mixed two models: `master_plan.md` §18 still assigned work as `Kişi A / Kişi B`, while `WORKDIVISION.md` already carried most of the real file-level split.
**Decision/learning:** Bumped `master_plan.md` to v0.4 and aligned both planning docs around two stable lanes: `Backend, Data & Agent` and `Frontend, UX & Demo`. Updated the daily plan, presentation ownership, collaboration wording, and branch naming so teammates can switch people without rewriting the plan.
**Why it matters:** Future planning updates should preserve lane ownership and handoff points instead of binding tasks to a specific person. If teammates rotate, keep the lane names and only change who is covering each lane that day.
**Reference:** `docs/master_plan.md` v0.4 §18/§21/§25, `WORKDIVISION.md` conventions and day sections.

### 2026-05-11 — Day 1 — Added a lightweight team tracking board

**Context:** After switching planning to responsibility lanes, the repo still lacked a short, day-to-day tracker that teammates could keep open while working.
**Decision/learning:** Added `TEAM_PROTOCOL.md` at the repo root as the live execution board. It summarizes the two lanes, daily status table, blockers, per-day checklists, handoff checkpoints, and ship gates. `WORKDIVISION.md` and `SETUP.md` now point to it.
**Why it matters:** Use `TEAM_PROTOCOL.md` for daily progress tracking and only drop to `WORKDIVISION.md` when you need the exact file list. This keeps task tracking lightweight without losing the detailed ownership map.
**Reference:** `TEAM_PROTOCOL.md`, `WORKDIVISION.md` header note, `SETUP.md` §9.

### 2026-05-11 — Day 1 — TEAM_PROTOCOL now pre-assigns the two default seats

**Context:** The first version of `TEAM_PROTOCOL.md` was trackable, but it still expected the team to decide the two daily owners each morning.
**Decision/learning:** Changed the board to a default two-seat model: `Seat 1 = Platform engineer / BDA` and `Seat 2 = Product engineer / FUD`. The daily board now shows pre-assigned work for each seat, and every day section starts with a short `Start here first` list so a teammate can begin work without planning overhead.
**Why it matters:** New teammates should open `TEAM_PROTOCOL.md` first, take their seat, and start with the top three items for that day. Only write an override when staffing actually changes.
**Reference:** `TEAM_PROTOCOL.md` default staffing section, daily board, and day checklists.

### 2026-05-11 — Day 1 — Single-owner rule added to planning docs

**Context:** Follow-up clarification from the team: task distribution must mean the total task set is partitioned across people, not that one task is jointly assigned to multiple owners.
**Decision/learning:** Updated `master_plan.md` to v0.5 and tightened `WORKDIVISION.md` and `TEAM_PROTOCOL.md` around a single-owner rule. Each task now has one explicit owner, handoff lines are producer-only delivery points, and Day 7 README ownership is fully on the FUD seat instead of split across both seats.
**Why it matters:** If a task appears in one lane or seat, the other lane may depend on its output but does not co-own the task. When a work item feels shared, split it into two separate tasks: producer delivery and consumer integration.
**Reference:** `docs/master_plan.md` v0.5 §18, `WORKDIVISION.md` conventions and Day 7, `TEAM_PROTOCOL.md` staffing and handoff sections.

### 2026-05-11 — Day 1 — TEAM_PROTOCOL simplified into numbered person-owned tasks

**Context:** The lane/seat structure still felt too abstract for daily use. Team feedback was explicit: list the work one task at a time and assign each task directly to Person A or Person B.
**Decision/learning:** Reworked the planning docs again. `master_plan.md` is now v0.6 and frames the build as a numbered task list split between two full-stack people. `TEAM_PROTOCOL.md` became the active task board with 12 concrete tasks, each with one owner, scope, files, dependency, and done criteria. `WORKDIVISION.md` was reduced to collaboration rules only.
**Why it matters:** Future planning changes should preserve the simple rule: one task, one owner, detailed in `TEAM_PROTOCOL.md`. If you need to rebalance workload, reassign whole tasks instead of creating partial co-ownership.
**Reference:** `docs/master_plan.md` v0.6 §18, `TEAM_PROTOCOL.md`, `WORKDIVISION.md`, `SETUP.md` §9.

## Day 2 — 12 May 2026 — Auth

### 2026-05-12 — Day 2 — Task 1 auth contract is live

**Context:** Implemented Task 1: FastAPI register/login/me, NextAuth credentials session carrier, protected app layout, and real login/register pages.
**Decision/learning:** Backend auth returns `{access_token, token_type, expires_in_days, user}` from register/login and `/api/auth/me` returns the same user shape without a token. NextAuth stores the FastAPI JWT as `session.backendToken`; client API calls read that token via `getSession()`. In Docker, NextAuth must call FastAPI through `NEXT_PRIVATE_API_URL=http://backend:8000`, while the browser keeps using `NEXT_PUBLIC_API_URL=http://localhost:8000`.
**Why it matters:** Task 2 transaction endpoints can depend on `Authorization: Bearer <session.backendToken>` and should not reintroduce localStorage token storage. Any server-side frontend call to the backend should use `NEXT_PRIVATE_API_URL` or the shared auth helper pattern.
**Reference:** `backend/app/routers/auth.py`, `frontend/lib/auth.ts`, `frontend/lib/api.ts`, `docker-compose.yml`.

### 2026-05-12 — Day 2 — Pin bcrypt below 5 for passlib

**Context:** Auth tests failed during bcrypt hashing after `passlib[bcrypt]` pulled `bcrypt==5.0.0`.
**Decision/learning:** Pinned `bcrypt>=4.2.0,<5.0.0` explicitly. Passlib 1.7.4 probes bcrypt internals and bcrypt 5 also rejects passlib's long test secret during backend detection, causing hashing to fail before requests complete.
**Why it matters:** Do not remove the explicit bcrypt pin unless passlib is replaced or upgraded to a version known to support bcrypt 5. If switching to argon2id later, update `backend/pyproject.toml`, auth helpers, and tests together.
**Reference:** `backend/pyproject.toml`, `backend/tests/test_auth.py`.

### 2026-05-12 — Day 2 — Frontend Docker image must use Node 22 for pnpm 11

**Context:** `docker compose up --build` failed in the frontend deps stage with `ERR_UNKNOWN_BUILTIN_MODULE: node:sqlite` because Corepack downloaded `pnpm@11.0.9` under `node:20-alpine`.
**Decision/learning:** Switched all frontend Docker stages to `node:22-alpine`, updated `SETUP.md`/`package.json` to require Node 22.13+, and copied `pnpm-workspace.yaml` into the Docker deps stage so pnpm sees the approved native build scripts. pnpm 11 uses APIs that are not available in Node 20.
**Why it matters:** Do not downgrade the frontend Dockerfile back to Node 20 while `packageManager` remains `pnpm@11.0.9`. If the team needs Node 20 support later, downgrade pnpm instead and test `pnpm install`, `pnpm build`, and Docker build together. Keep `pnpm-workspace.yaml` in the deps-stage COPY list, or Docker builds will fail with `ERR_PNPM_IGNORED_BUILDS`.
**Reference:** `frontend/Dockerfile`, `frontend/package.json`, `SETUP.md`.

### 2026-05-12 — Day 2 — Backend Docker deps install skips project package

**Context:** After the frontend Docker fix, `docker compose up --build` failed in the backend deps stage because `uv sync` tried to build the project before source files existed and `backend/pyproject.toml` references `../README.md`, which is outside the backend Docker context.
**Decision/learning:** Backend Docker now creates the expected parent README path inside the image and runs `uv sync --no-install-project` for the dependency cache layer. The app source is copied afterward, and container startup uses `uvicorn` directly from `/opt/venv` instead of `uv run uvicorn`.
**Why it matters:** Keep the backend deps layer free of source-file requirements; otherwise every app edit busts the dependency cache or Docker builds fail on package metadata. `uv run alembic ...` inside a running container still works because app source and `/README.md` exist by then.
**Reference:** `backend/Dockerfile`, `docker-compose.yml`, `backend/pyproject.toml`.

### 2026-05-12 — Day 2 — Task 2 uses real transaction data only

**Context:** Implemented Task 2 transaction CRUD and replaced visible hardcoded finance examples after team feedback that mock data should not appear on the site.
**Decision/learning:** The dashboard now reads/writes `/api/transactions` with the NextAuth-carried FastAPI token, computes visible summaries from returned DB rows, and shows Turkish empty states when there is no data. Static finance examples were removed from dashboard, chat, receipts, and family pages; future demo data should be seeded into a demo account with `is_demo=true`, not embedded in React components.
**Why it matters:** New UI work should treat empty states as acceptable but avoid fake merchants, amounts, family members, or tool traces in visible app pages. If a demo scenario needs sample records, create them in the database and keep them user-scoped.
**Reference:** `backend/app/routers/transactions.py`, `frontend/components/dashboard-client.tsx`, `frontend/components/ChatStream.tsx`.

### 2026-05-12 — Day 2 — Theme toggle is binary light/dark

**Context:** The previous theme button cycled `light → dark → system`, which could feel like a missed click when the resolved system theme matched the previous visual state.
**Decision/learning:** The toggle now uses `resolvedTheme` and switches directly between `light` and `dark` in one click. The button is disabled until mounted to avoid hydration mismatch.
**Why it matters:** Do not reintroduce a three-state cycle unless the UI clearly exposes the `system` state separately.
**Reference:** `frontend/components/theme-toggle.tsx`.

### 2026-05-12 — Day 2 — Categories, analytics, and recurring payments stay DB-backed

**Context:** Extended the transaction dashboard with predefined/custom categories, a monthly income/expense status panel, category pie chart, and recurring payment management.
**Decision/learning:** Added `/api/categories`, `/api/transactions/summary`, and `/api/subscriptions` with the same user-scope helper used by transaction CRUD. System categories are seeded by migration `0002_system_categories`; custom categories are user-owned and can shadow defaults by name. The first dashboard charts are lightweight SVG/CSS driven from API responses instead of adding a chart dependency.
**Why it matters:** Future dashboard work should keep visible analytics DB-backed and Turkish-empty-state based; do not reintroduce hardcoded chart data. Subscription monthly equivalents currently use simple MVP math (`weekly * 4`, `yearly / 12`) and should be refined only if the master plan asks for calendar-accurate billing analysis.
**Reference:** `backend/app/routers/categories.py`, `backend/app/routers/transactions.py`, `backend/app/routers/subscriptions.py`, `frontend/components/dashboard-client.tsx`.

### 2026-05-12 — Day 2 — Panel split into focused dashboard subpages

**Context:** The expanded dashboard became too dense and appeared narrow on wide screens when everything lived on `/dashboard`.
**Decision/learning:** Kept `/dashboard` as the analytics overview and moved data-entry flows to `/dashboard/transactions` and `/dashboard/recurring`, all backed by the same DB-driven dashboard client. The authenticated app shell now lets content use the available width instead of centering inside `max-w-7xl`.
**Why it matters:** Future dashboard additions should prefer focused subpages over stacking more forms on the overview. Keep the sidebar and in-page dashboard tabs aligned when adding new panel sections.
**Reference:** `frontend/app/(app)/layout.tsx`, `frontend/components/sidebar.tsx`, `frontend/components/dashboard-client.tsx`.

## Day 3 task work — 12 May 2026 — Agent stream

### 2026-05-12 — Day 3 prep — SSE stream uses scoped tools and lazy LangGraph wiring

**Context:** Implemented Task 3 and Task 4: spending/subscription/memory tools, Turkish TL/date helpers, chat SSE endpoint, typed frontend stream client, tool trace UI, and reusable dashboard chart/banner components.
**Decision/learning:** The `/api/chat/stream` request accepts only the user message and optional `conversation_id`; it never accepts `user_id`. The deterministic stream path calls the same scoped tool functions used by the LangGraph wrappers, while `backend/app/agent/graph.py` builds the Gemini/LangGraph graph lazily so tests and local startup do not require a Gemini key. LangGraph tool wrappers inject `user_id` from state with `InjectedState`.
**Why it matters:** Future agent work should keep `user_id` out of request bodies and prompts. If the LLM path is expanded, reuse the existing tool builders instead of adding a second DB-query path, and preserve the documented SSE event names in `docs/agent_sse_example.json` for the frontend.
**Reference:** `backend/app/services/agent_runner.py`, `backend/app/agent/tools.py`, `backend/app/agent/graph.py`, `backend/app/routers/chat.py`, `frontend/lib/sse.ts`, `frontend/components/ChatStream.tsx`, `docs/agent_sse_example.json`.

### 2026-05-12 — Day 3 prep — OpenRouter provider added as Gemini fallback

**Context:** Added an alternative path for using Gemini-class models through OpenRouter instead of the direct Gemini API.
**Decision/learning:** Bumped `master_plan.md` to v0.7 and added `LLM_PROVIDER=gemini|openrouter`. Direct Gemini remains default. OpenRouter uses `langchain-openai` with `base_url=https://openrouter.ai/api/v1`, `OPENROUTER_API_KEY`, default model `google/gemini-2.5-flash`, and optional attribution headers from env. No API key is stored outside environment variables.
**Why it matters:** Future LLM/OCR work should read provider settings from `Settings` and should not hardcode Gemini-only clients. When `LLM_PROVIDER=openrouter`, missing `OPENROUTER_API_KEY` should fail fast at graph construction.
**Reference:** `docs/master_plan.md` v0.7 §10/§13/§22, `backend/app/config.py`, `backend/app/agent/graph.py`, `.env.example`, `SETUP.md`.

## Day 4 task work — 12 May 2026 — Receipt upload

### 2026-05-12 — Day 4 — Receipt OCR candidate and confirmation flow

**Context:** Implemented Task 5 and Task 6: receipt upload, MinIO storage, OCR candidate extraction, edit-before-save confirmation, and receipt history.
**Decision/learning:** No schema migration was needed because `transactions` already had `source`, `receipt_image_url`, and `raw_ocr_data`. `/api/receipts/upload` stores the file first, then returns a structured candidate; confirmation uses the existing `/api/transactions` create path with `source=receipt_ocr`. The OCR service supports direct Gemini or OpenRouter through the existing `LLM_PROVIDER` settings. A text receipt fixture keeps tests deterministic; real browser image OCR requires a configured provider key.
**Why it matters:** Keep receipt confirmation user-approved; do not write a transaction from upload alone. Raw OCR data may be stored on the user-scoped transaction but must not be logged, and receipt base64 should not be persisted in chat/tool traces.
**Reference:** `backend/app/routers/receipts.py`, `backend/app/services/ocr.py`, `backend/app/services/minio.py`, `frontend/components/ReceiptUploader.tsx`, `frontend/components/ReceiptConfirmDialog.tsx`, `TEAM_PROTOCOL.md`.

## Day 5/6 task work — 12 May 2026 — Family, live agent, proactive insights

### 2026-05-12 — LangGraph route is active with scoped fallback

**Context:** Connected `/api/chat/stream` to the existing LangGraph Gemini/OpenRouter graph while preserving the deterministic scoped stream for missing keys or runtime failures.
**Decision/learning:** The route now prefers the live graph when the selected provider key exists, streams the same SSE event shape, and falls back to scoped tool answers with a Turkish setup notice when `GEMINI_API_KEY` or `OPENROUTER_API_KEY` is missing. Tests force LLM keys empty in `tests/conftest.py` so they never call external providers accidentally.
**Why it matters:** Keep the deterministic stream path alive as the no-secret/no-network demo fallback. Future chat tools should preserve the existing `message_start`, `tool_call`, `tool_result`, `delta`, and `done` event names because the frontend depends on them.
**Reference:** `backend/app/services/agent_runner.py`, `backend/tests/conftest.py`, `frontend/lib/sse.ts`, `frontend/components/ChatStream.tsx`.

### 2026-05-12 — Chat receipt analysis reuses OCR candidate logic

**Context:** Receipt parsing had only been reachable from `/api/receipts/upload`; chat can now receive an attached receipt image and show the `analyze_receipt` tool trace.
**Decision/learning:** Chat calls `build_receipt_candidate` directly and returns the same structured candidate fields as the upload flow, but does not create a transaction. `raw_ocr_data` is reduced to provider/source filename in agent/tool traces, and base64/raw text are redacted from persisted tool payloads.
**Why it matters:** The edit-before-save rule still belongs to `/receipts`; chat is an analysis surface only. Do not add automatic transaction writes from chat without updating the master plan and privacy copy first.
**Reference:** `backend/app/agent/tools.py`, `backend/app/services/agent_runner.py`, `backend/tests/test_chat_stream.py`, `frontend/components/ChatStream.tsx`.

### 2026-05-12 — Family switch uses a client-side active child token

**Context:** Implemented parent-managed child profiles and the family switch UI without changing the existing NextAuth parent session.
**Decision/learning:** `/api/family/switch/{child_id}` returns a normal FastAPI JWT for the child. The frontend stores only the active child token/user in `localStorage` under `cuzdan-kocu.active-profile`; API helpers use it by default, while family-management calls opt out with `useActiveProfile:false` so the parent can keep managing profiles.
**Why it matters:** Child accounts still have no password and do not log in directly. When debugging dashboard/chat scope, check the active profile banner and localStorage key before assuming the backend scope filter is wrong.
**Reference:** `backend/app/routers/family.py`, `frontend/lib/active-profile.ts`, `frontend/lib/api.ts`, `frontend/components/ActiveProfileBanner.tsx`, `frontend/components/FamilyClient.tsx`.

### 2026-05-12 — Proactive insights are API-backed and scheduler-ready

**Context:** Replaced the static dashboard insight banner with `/api/insights` data and added a scheduler-ready worker/manual refresh path.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.8 because the implemented insight type set differs from the older glossary. Current rules generate `low_activity`, `monthly_status`, `spending_spike`, `category_overspending`, `upcoming_recurring`, `savings_opportunity`, and `receipt_activity`. The deploy scheduler is not wired yet; use `uv run python -m app.workers.proactive` or `POST /api/insights/refresh` until production cron is configured.
**Why it matters:** Task 9 still has deployment work left: live HTTPS URL and production demo seed. The backend/API/UI worker pieces are ready, but the production scheduler should be documented in the deploy PR once the platform is chosen.
**Reference:** `docs/master_plan.md` v0.8, `backend/app/services/insights.py`, `backend/app/routers/insights.py`, `backend/app/workers/proactive.py`, `frontend/components/dashboard-client.tsx`, `TEAM_PROTOCOL.md`.

### 2026-05-12 — Day 6 — Deploy handoff and mobile polish

**Context:** Continued Day 6 after a split handoff: proactive insight code was already in place, but deploy/prod seed and mobile/dark polish were incomplete.
**Decision/learning:** Added `docker-compose.prod.yml`, `coolify.yaml`, and `docs/deploy.md` as the production handoff. Demo seeding now lives in `backend/app/workers/demo_seed.py`, keeps `seeds/demo_family.py` as a wrapper, supports `DEMO_*` env overrides, creates `is_demo=true` Ayşe/Mehmet parent demo accounts plus Elif as Ayşe's child profile, refreshes insights after seeding, and recognizes legacy local demo emails if a dev DB was seeded before the credential alignment. Task 10 UI polish is done in repo, but Task 9 remains platform-blocked until a real HTTPS URL and production DB seed are verified outside the local workspace.
**Why it matters:** For production, set `DEMO_PARENT_PASSWORD`, run migrate, run `demo-seed`, run `proactive-worker`, then verify `https://<backend>/health` and login as `ayse@demo.cuzdan-kocu.app`. Do not mark Task 9 fully done until that platform verification is complete.
**Reference:** `docker-compose.prod.yml`, `coolify.yaml`, `docs/deploy.md`, `backend/app/workers/demo_seed.py`, `frontend/app/globals.css`, `TEAM_PROTOCOL.md`.

### 2026-05-12 — Day 6 — OpenRouter headers must stay ASCII

**Context:** Uploading a real image receipt with `LLM_PROVIDER=openrouter` failed before the provider request was sent.
**Decision/learning:** The OpenAI/httpx client encodes HTTP header values as ASCII. `OPENROUTER_APP_TITLE=Cüzdan Koçu` caused `UnicodeEncodeError` when OCR built `X-Title`/OpenRouter headers. OCR now uses the same ASCII-safe header normalization as chat and wraps provider invocation failures as `ReceiptOcrUnavailableError`, so `/api/receipts/upload` returns a Turkish 503 instead of a raw 500.
**Why it matters:** Keep OpenRouter attribution headers ASCII-safe. Turkish user-facing product text is still required, but environment values that become HTTP headers must be normalized before passing them to `ChatOpenAI`.
**Reference:** `backend/app/services/ocr.py`, `backend/app/agent/graph.py`, `backend/tests/test_ocr.py`, `backend/tests/test_agent_graph.py`.

## Day 7 product polish — 13 May 2026 — Unified money entry and family/account controls

### 2026-05-13 — Day 7 — Polish scope added in master plan v0.9

**Context:** Added post-Day-6 product polish requested for the demo: merge `İşlemler` and `Tekrarlar`, collapse the left panel, edit account info, and show a parent-only family financial overview.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.9 before coding because these are new core-scope UX/API surfaces. `/dashboard/recurring` now redirects to `/dashboard/transactions`; the unified `İşlemler` screen keeps one-time transactions and recurring payments in one place with a mode selector. Account editing lives at `/account` and updates the NextAuth session after `PATCH /api/auth/me`. The family overview uses `GET /api/family/overview`, is parent-only, and summarizes parent plus child rows with the existing user-scope rules.
**Why it matters:** Do not re-add a separate `Tekrarlar` menu unless the master plan is updated again. Future account settings must preserve child restrictions: child profile finance level/password changes are still blocked. Future family analytics should build on `/api/family/overview` instead of bypassing the parent-only guard.
**Verification:** `docker compose run --rm -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/backend/tests:/app/tests -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/seeds:/seeds backend uv run pytest -q` passed with 49 tests. `docker compose run --rm backend uv run mypy app`, `docker compose run --rm -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/backend/tests:/app/tests backend uv run ruff check app tests`, `docker build --target builder -t btk-hackathon-frontend-builder ./frontend`, and `docker run --rm btk-hackathon-frontend-builder pnpm format:check` passed.
**Reference:** `docs/master_plan.md` v0.9, `backend/app/routers/auth.py`, `backend/app/routers/family.py`, `frontend/components/dashboard-client.tsx`, `frontend/components/sidebar.tsx`, `frontend/components/AccountClient.tsx`, `frontend/components/FamilyClient.tsx`.

### 2026-05-13 — Day 7 — Stamp-label color override + family-page active badge fix

**Context:** On the family page after switching into a child profile, the "Aktif çocuk modu" badge rendered as an empty pill and the row below it looked lopsided/blended. Reported via screenshot from dark mode.
**Decision/learning:** Two coupled problems. (1) `.stamp-label` in `frontend/app/globals.css` declared `color: oklch(var(--primary))` directly in `@layer utilities`. Because the rule sat in the same cascade layer as Tailwind utilities and was sourced after them, its color always won over `text-primary-foreground` — so `<span className="stamp-label bg-primary text-primary-foreground">…` rendered primary-on-primary and the text disappeared. Fix: move the default color into a `:where(.stamp-label)` rule so it has specificity 0,0,0 and any Tailwind `text-*` utility wins; the stamp keeps its tilt/border/typography but callers can now safely recolor. (2) The active badge plus the `sm:grid-cols-[9.5rem_9.5rem_auto]` row with a `sm:col-span-3` "Bu profile geç" button looked distorted because the badge was rotated, the wide button sat directly below three narrow controls of differing heights, and the disabled (active) state used the same primary green as the badge so they blended. Fix: introduced a dedicated `.badge-active` pill (no rotation, accent-tinted, separate from the brand stamp), moved the badge to its own row beside the name, switched the controls row to `minmax(0,1fr)_minmax(0,1fr)_auto` so the date and select grow evenly, and made "Bu profile geç" a separate full-width button — `variant="secondary"` with "Bu profilde aktifsin" label when the row's profile is already active. The active card and the action button no longer share the same color.
**Why it matters:** Do not re-add `color:` to the `.stamp-label` body block — keep the default inside `:where()` or the override-by-Tailwind contract breaks again. The kid-mode override of `.stamp-label` already lives under a `[data-kid-mode="on"]` selector and was not affected; do not consolidate it into the `:where()` rule. When you need an inline status pill on a colored background, prefer `.badge-active` (or a new sibling class) over `stamp-label` so callers do not have to fight specificity.
**Verification:** `docker build --target builder -t btk-hackathon-frontend-builder ./frontend` and `docker run --rm btk-hackathon-frontend-builder pnpm lint / pnpm type-check / pnpm format:check` all clean. `docker compose build frontend && docker compose up -d frontend` recreated the running container. `curl http://localhost:3000/family` returns 307 → /login as expected for unauthenticated requests.
**Reference:** `frontend/app/globals.css` (`:where(.stamp-label)` + `.badge-active`), `frontend/components/FamilyClient.tsx` (active-child card layout).

### 2026-05-13 — Day 7 — Login-page demo selector with all 4 perspectives

**Context:** To validate the user-scope rules (İK-4..İK-8) and showcase the kid lite-mode UI, every demo persona needs to be reachable from the login screen without the parent-only family-switch path. Today only Ayşe and Mehmet had passwords; child profiles were password-less by design (Day 1 decision).
**Decision/learning:** Extended `app.workers.demo_seed` to also set a real `password_hash` on the three demo child accounts (Elif, Deniz, Zeynep) and added a new individual demo persona `kerem@demo.cuzdan-kocu.app` (Kerem Demir, 23, role=`individual`). All six accounts remain `is_demo=true`. **This is demo-only** — child accounts created at runtime through `POST /api/family` still get `password_hash=None`; the constraint that real children authenticate only via parent family-switch is unchanged. Added `GET /api/auth/demo-accounts` (unauthenticated) which returns the password alongside metadata (role, age, age_status, finance_level, family_label, tagline). The endpoint filters strictly on `is_demo=True` and on a whitelisted set of demo emails sourced from the seeder helpers, so a future non-demo user cannot accidentally leak credentials. The login page now fetches this list and renders four grouped buttons: "Aile — Ebeveynler", "Aile — 18 yaş altı çocuklar", "Aile — 18 yaş üstü çocuklar", "Bireysel hesap". Click → fills credentials and calls `signIn("credentials")`. Updated `tests/test_demo_seed.py` to assert the new user count (6), the Kerem isolation (parent_id/family_id are None), the universal `password_hash is not None` invariant for demo accounts, the new transaction (15) and subscription (4) totals, and that `refresh_insights_for_user` is called for Kerem too.
**Why it matters:** Do not enable login for non-demo child accounts. The demo password disclosure is acceptable **only because** `is_demo=True` rows are seeder-managed and not real users; the endpoint's `is_demo` filter is the load-bearing safety guarantee — keep it. If a new demo account is added to the seeder, also add its email to `_demo_account_taglines()` in `app/routers/auth.py` or it won't show up in the selector. Frontend uses `account.age_status` (not `role`) to decide the "18 yaş altı/üstü çocuk" bucket so the lite-mode trigger (`[[kid-lite-mode-ui]]`) stays consistent.
**Docker / runtime:** Rebuilt `backend` and `frontend` compose services (`docker compose build && docker compose up -d`). After rebuild, run `docker compose exec -T backend uv run alembic upgrade head` (no new migration today) and `docker compose exec -T backend uv run python -m app.workers.demo_seed` to refresh the demo data so the new accounts and the Kerem rows exist. Smoke-checked `GET http://localhost:8000/api/auth/demo-accounts` (200, 6 rows) and `POST /api/auth/login` with Elif and Kerem credentials.
**Verification:** `docker compose run --rm -v $(pwd)/backend/tests:/app/tests -v $(pwd)/seeds:/seeds backend uv run pytest -q` → 51 passed. `docker compose run --rm backend uv run mypy app` clean. `docker compose run --rm -v $(pwd)/backend/tests:/app/tests backend uv run ruff check app tests` clean. `docker run --rm btk-hackathon-frontend-builder pnpm lint / pnpm type-check / pnpm format:check` all clean (rebuilt the builder image with `docker build --target builder -t btk-hackathon-frontend-builder ./frontend`).
**Reference:** `backend/app/workers/demo_seed.py` (Kerem + child demo passwords + helper functions), `backend/app/routers/auth.py` (`/api/auth/demo-accounts`), `backend/app/schemas/auth.py` (`DemoAccount`), `backend/tests/test_demo_seed.py`, `frontend/components/auth/login-form.tsx`, `frontend/app/(auth)/login/page.tsx`, `frontend/lib/types.ts` (`DemoAccount`).

### 2026-05-13 — Day 7 — Kid lite mode (UI) for minors (master plan v0.11)

**Context:** Family feedback that the standard ledger/receipt-tape UI is too dense for under-18 users (Elif persona). Children should see a friendlier, simpler surface even though backend scope rules are identical.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.11 and added §12.2.13 "Çocuk lite mod (UI)". The lite mode is purely frontend: `frontend/lib/kid-mode.tsx` introduces `KidModeProvider` (wraps the `(app)` layout) and `useKidMode()`. The provider watches the NextAuth session and the active-profile localStorage (`ACTIVE_PROFILE_EVENT`), so both direct child logins and parent → child family-switches flip the mode. The trigger is **`age_status === "minor"` only** — `role='child'` alone is not enough, because v0.10 allows adult children. When on, `data-kid-mode="on"` is set on `<html>` and `globals.css` overrides the OKLCH theme tokens (softer purples/peach/teal, larger radius), neutralizes the ledger/receipt-tape/binder-holes textures, and adds `.kid-balance-bubble` / `.kid-chip` / `.kid-hero-title` utilities. Sidebar uses a separate `KID_NAV_ITEMS` set with Turkish kid-language labels (Cüzdanım, Hareketler, Koç, Fişlerim, Profilim) and hides `/family`. `DashboardClient` swaps in a kumbara-themed hero, drops the 4th "Aylık tekrar" envelope, forces `entryMode="one_time"`, hides the new-category creator, the SummaryStatus + SpendingChart row, and the entire recurring-subscriptions section. `ChatStream` hides the "Araç izi" panel and uses kid-friendly intro/placeholder copy; `ChatHero` and `ReceiptHero` are new client wrappers that swap heading copy without converting the route to a client component.
**Why it matters:** Do not gate kid mode on `role` alone — adult children must keep the classic UI. Do not add a new endpoint or schema column; the lite mode is purely a presentation layer over the same user-scoped APIs (İK-4..İK-8 unchanged). Future child-only UI work should also use `useKidMode()` rather than introducing a second gate. The agent prompt path is unchanged — finance_level=child already drives kid wording at the LLM layer (A-3), so no agent/system prompt changes were made.
**Verification:** `docker build --target builder -t btk-hackathon-frontend-builder ./frontend` succeeded (includes `next build`); `docker run --rm -v $(pwd)/frontend/components:/app/components -v $(pwd)/frontend/app:/app/app -v $(pwd)/frontend/lib:/app/lib btk-hackathon-frontend-builder pnpm lint`, `pnpm type-check`, and `pnpm format:check` all clean. Backend untouched.
**Reference:** `docs/master_plan.md` v0.11 §12.2.13, `frontend/lib/kid-mode.tsx`, `frontend/app/(app)/layout.tsx`, `frontend/app/globals.css` (`[data-kid-mode="on"]` block + `.kid-*` utilities), `frontend/components/sidebar.tsx`, `frontend/components/dashboard-client.tsx`, `frontend/components/ChatStream.tsx`, `frontend/components/ChatHero.tsx`, `frontend/components/ReceiptHero.tsx`.

### 2026-05-13 — Day 7 — Birth dates, adult children, and custom recurrence

**Context:** Extended the family and recurring-payment model after the first Day 7 polish pass.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.10 before coding because this changes schema and product invariants. `users.age` is replaced by `users.birth_date`; API responses compute `age` and `age_status` dynamically. `role='child'` now means family relationship only, so adult children stay valid child profiles with `age_status='adult'`. Multi-parent demo families share a `family_id`, while legacy parent/child data still falls back to `parent_id`. Recurring payments now support `billing_cycle='custom'` with `recurrence_interval` and `recurrence_unit`, and monthly equivalents go through the shared recurrence helper. Migration gotchas: Alembic revision IDs must fit the existing `alembic_version.version_num VARCHAR(32)`, and convention-named checks should be dropped with `op.f(...)`.
**Why it matters:** Do not reintroduce editable age fields; all UI and validation should ask for birth date when age-related logic is needed. Do not assume a child profile is legally minor. Future subscription analytics should use `monthly_equivalent(...)` instead of hard-coded weekly/monthly/yearly math.
**Verification:** `docker compose run --rm -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/backend/tests:/app/tests -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/seeds:/seeds backend uv run pytest -q` passed with 51 tests. `docker compose run --rm backend uv run mypy app`, `docker compose run --rm -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/backend/tests:/app/tests backend uv run ruff check app tests`, `docker build --target builder -t btk-hackathon-frontend-builder ./frontend`, `docker run --rm btk-hackathon-frontend-builder pnpm format:check`, `docker compose run --rm backend uv run alembic upgrade head`, and `docker compose run --rm backend uv run python -m app.workers.demo_seed` passed.
**Reference:** `docs/master_plan.md` v0.10, `backend/alembic/versions/0003_birth_date_family_and_recurrence.py`, `backend/app/utils/age.py`, `backend/app/utils/recurrence.py`, `backend/app/workers/demo_seed.py`, `frontend/components/FamilyClient.tsx`, `frontend/components/dashboard-client.tsx`.

### 2026-05-13 — Day 7 — Chat charts, history, memory, and concept images completed

**Context:** Finishing an interrupted Agenta pass for chat image tool calls, inline data visualization, chat history, and memory visibility.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.13 to align the §16 LangGraph tool skeleton with the already-approved v0.12 scope. Registered the new `/api/conversations` and `/api/memory` routers, kept chat history and memory strictly current-profile scoped (parents must family-switch into a child profile to view that child context), and tightened `/api/chat/stream` conversation continuation to `Conversation.user_id == current_user.id`. `visualize_spending` returns chart point values as strings from Python to preserve the no-float money invariant; the frontend parses those strings for Recharts rendering. `illustrate_concept` uses direct Gemini image generation plus MinIO and returns an `image` SSE event only for coach-mode concept visuals; OpenRouter can still power chat, but concept images require `GEMINI_API_KEY`. The deterministic fallback now handles memory questions, chart requests, and concept illustration requests without trusting `user_id` from the prompt. The local shell had `node`/`npm` but no `corepack` or `pnpm`, so Recharts was added and checks were run through `npx pnpm@11.0.9 ...`.
**Why it matters:** Do not change chart values back to Python floats. Keep image generation separate from spending charts and investment/product prompts; it is for educational concept illustrations only and has a per-user daily limit. If production enables image generation, configure `GEMINI_IMAGE_MODEL`, `MINIO_BUCKET_ILLUSTRATIONS`, and `ILLUSTRATION_DAILY_LIMIT` alongside the existing Gemini/MinIO settings.
**Verification:** `docker compose run --rm -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/backend/tests:/app/tests -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/seeds:/seeds backend uv run pytest -q` passed with 57 tests. `docker compose run --rm -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/backend/tests:/app/tests backend uv run ruff check app tests` passed. `docker compose run --rm backend uv run mypy app` passed. `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 format:check`, and `npx pnpm@11.0.9 build` passed; build still prints the existing Next.js flat-config plugin warning.
**Reference:** `backend/app/agent/tools.py`, `backend/app/services/agent_runner.py`, `backend/app/services/image_gen.py`, `backend/app/routers/conversations.py`, `backend/app/routers/memory.py`, `frontend/components/ChatStream.tsx`, `frontend/components/ChatChart.tsx`, `frontend/components/ChatHistoryClient.tsx`, `frontend/components/MemoryViewer.tsx`, `docs/master_plan.md` v0.13.

### 2026-05-13 — Day 7 — OpenRouter Gemini 3.1 model split

**Context:** Local `.env` was switched to `LLM_PROVIDER=openrouter`, then chat/image model names needed to move to Gemini 3.1 OpenRouter IDs.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.14. OpenRouter chat now defaults to `google/gemini-3.1-flash-lite`, and OpenRouter image generation uses a separate `OPENROUTER_IMAGE_MODEL=google/gemini-3.1-flash-image-preview`. `IllustrationService` now routes concept images through OpenRouter `/chat/completions` when `LLM_PROVIDER=openrouter`, while direct Gemini mode still uses `GEMINI_IMAGE_MODEL` and `GEMINI_API_KEY`.
**Why it matters:** Do not put OpenRouter model IDs with the `google/` prefix into the direct Gemini API path unless Google changes its model naming. In OpenRouter mode, concept images require `OPENROUTER_API_KEY`; `GEMINI_API_KEY` is no longer required for that path.
**Reference:** `backend/app/config.py`, `backend/app/services/image_gen.py`, `.env.example`, `docker-compose.yml`, `docs/master_plan.md` v0.14.

### 2026-05-13 — Day 7 — Illustration MinIO bucket must be browser-readable

**Context:** Live OpenRouter concept image generation returned an `image` SSE event and stored the object in MinIO, but the generated `http://localhost:9000/illustrations/...` URL returned `403 AccessDenied` in the browser path.
**Decision/learning:** `IllustrationService` now applies a public read-only bucket policy (`s3:GetObject` on `arn:aws:s3:::<illustrations-bucket>/*`) before saving illustration objects. This is limited to educational illustration images; receipt storage remains unchanged.
**Why it matters:** Future image work should verify both provider generation and browser fetchability. If production changes `MINIO_BUCKET_ILLUSTRATIONS` or resets MinIO policy, the first illustration save will re-apply the policy; direct receipt image public-read should not be copied from this path without a privacy review.
**Verification:** OpenRouter chat smoke test returned `message_start/tool_call/tool_result/delta/done`; concept prompt returned `explain_concept`, `illustrate_concept`, and `image`; the generated image URL returned HTTP 200 with `image/jpeg` after policy application. `docker compose run --rm -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/backend/tests:/app/tests -v /Users/omerfarukaltinova/Git_Projects/btk-hackathon/seeds:/seeds backend uv run pytest -q` passed with 58 tests.
**Reference:** `backend/app/services/image_gen.py`, `backend/tests/test_image_gen.py`.

### 2026-05-13 — Day 7 — Chat context replay and compact scroll surfaces

**Context:** Continued chat polish after users noticed the assistant did not behave as if it knew previous turns, and long chats/history pages made the whole page scroll and feel crowded.
**Decision/learning:** The live LangGraph path now rebuilds the last 20 `user`/`assistant` messages from the current conversation before invoking the model, replacing the current persisted user row with the receipt-augmented prompt when needed. Tool rows stay out of model context because standalone `ToolMessage` history without matching tool-call IDs can break provider/tool semantics. The chat page hydrates the latest conversation (or the session-stored active conversation) on load, exposes a clear `Yeni sohbet` reset, and moves chat/tool trace into internal tabs with fixed scroll regions. The history page now uses a compact archive list plus a separately scrollable message pane instead of large stacked cards.
**Why it matters:** Future chat tools should preserve `conversation_id` continuation and keep context replay scoped to `Conversation.user_id == current_user.id`. If persisted tool context is ever needed, add a provider-safe summarization layer rather than replaying raw tool messages into LangGraph.
**Verification:** Backend `ruff`, `mypy`, and full `pytest -q` passed with 59 tests. Frontend `pnpm lint`, `pnpm type-check`, `pnpm format:check`, and `docker build --target builder -t btk-hackathon-frontend-builder ./frontend` passed.
**Reference:** `backend/app/services/agent_runner.py`, `backend/tests/test_chat_stream.py`, `frontend/components/ChatStream.tsx`, `frontend/components/ChatHistoryClient.tsx`, `frontend/components/ChatHero.tsx`, `frontend/app/(app)/chat/page.tsx`.

### 2026-05-13 — Day 7 — Chat history can resume, delete, and replay attachments

**Context:** Extended the chat history polish so a user can clean up old chats, resume a specific archived thread, and see old chart/image tool outputs again.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.15. `GET /api/conversations/{id}/messages` now returns sanitized `attachments` derived from persisted tool results (`chart` specs and `image_url`/`alt_text` only), and `DELETE /api/conversations/{id}` deletes only conversations owned by the current profile. The frontend uses session storage to mark the conversation to resume when navigating from history back to `/chat`; deleting that active conversation clears the session pointer. Chat prompt suggestions now rotate with a small CSS animation, with reduced-motion covered by the existing global media query.
**Why it matters:** Keep historical attachment replay sanitized; do not expose raw `tool_calls` wholesale to the UI. Resume/delete must stay current-profile scoped, matching the stricter chat privacy model. If MinIO object deletion for historical concept images becomes required, add it deliberately as a storage-cleanup task instead of bundling it into DB deletion silently.
**Verification:** Live demo smoke created Ayşe conversation `4d79a175-f8ee-4066-a293-4a0701dde55a` and observed all tools through `/api/chat/stream`: `analyze_receipt`, `get_spending`, `get_subscriptions`, `get_user_memory`, `visualize_spending`, `explain_concept`, `illustrate_concept`, `simulate_scenario`. A disposable demo chat deleted with 204. The history endpoint returned `chart` and `image` attachments, and the historical image URL fetched as HTTP 200 `image/jpeg`. Backend `ruff`, `mypy`, full `pytest -q` (61 tests), frontend `lint`, `type-check`, `format:check`, and Docker frontend build passed.
**Reference:** `docs/master_plan.md` v0.15, `backend/app/routers/conversations.py`, `backend/app/schemas/conversation.py`, `backend/tests/test_conversations.py`, `frontend/components/ChatHistoryClient.tsx`, `frontend/components/ChatStream.tsx`, `frontend/lib/chat-attachments.ts`, `frontend/lib/chat-session.ts`.

### 2026-05-13 — Day 7 — Local Docker DB migrated and Alembic metadata drift fixed

**Context:** Rehydrated a local Docker environment after remote commits and checked whether the persisted Postgres volume matched the current schema/demo seed.
**Decision/learning:** The local DB was still at `0002_system_categories`; `alembic upgrade head` brought it to `0003_birth_recurrence`. After migration, `alembic check` reported drift because ORM metadata did not declare `idx_users_family` and represented the `idx_tx_user_date` / `idx_insight_user` timestamp expressions without `DESC`, even though the migrations had already created the correct DB indexes. Updated the model metadata only; no new migration was required.
**Why it matters:** When using `alembic check` as the source-of-truth drift test, keep expression/partial indexes represented exactly in SQLAlchemy metadata or Alembic will propose destructive index churn. For an existing dev DB, run `alembic upgrade head` before demo seeding so the seeder can write `birth_date`, `family_id`, and custom recurrence rows.
**Verification:** `docker compose up -d --build`, `docker compose exec -T backend alembic upgrade head`, `docker compose exec -T backend alembic check`, `docker compose exec -T backend python -m app.workers.demo_seed`, backend `/health`, frontend `/login`, all six `/api/auth/demo-accounts` logins, DB seed counts (6 demo users, 15 seeded transactions, 4 subscriptions), and `uv run ruff check app tests && uv run mypy app && uv run pytest -q` all passed.
**Reference:** `backend/app/models/user.py`, `backend/app/models/transaction.py`, `backend/app/models/insight.py`, `backend/alembic/versions/0003_birth_date_family_and_recurrence.py`, `backend/app/workers/demo_seed.py`.

### 2026-05-13 — Day 7 — Parent-only family overview gained expandable member details

**Context:** The family page needed more individual-level finance visibility inside the parent overview while preserving the rule that only parents can see family-wide data.
**Decision/learning:** Extended the existing parent-only `GET /api/family/overview` response instead of adding a new endpoint. Each member row now includes expense share, active recurring count, receipt-sourced transaction count, and latest transaction metadata. The frontend keeps aggregate family cards visible and adds an explicit `Kişi detayını aç` toggle for per-profile details.
**Why it matters:** Keep this data behind `_ensure_parent`; children should still receive 403 from `/api/family/overview` and must use their own dashboard/profile context for personal data. Future family analytics should extend the same overview contract unless a genuinely separate use case appears.
**Verification:** `uv run pytest tests/test_family.py -q`, `uv run ruff check app tests`, `uv run mypy app`, full `uv run pytest -q`, `pnpm lint`, `pnpm type-check`, `pnpm format:check`, `docker compose up -d --build frontend`, and an Ayşe demo `/api/family/overview` smoke check all passed.
**Reference:** `backend/app/routers/family.py`, `backend/app/schemas/family.py`, `frontend/components/FamilyClient.tsx`, `frontend/lib/types.ts`, `backend/tests/test_family.py`.

### 2026-05-13 — Day 7 — Family overview details became progressive disclosure with charts

**Context:** Follow-up family page polish: when parent-only details are hidden, member names/basic information should remain visible; opening details should add charts and deeper statistics rather than replacing the whole section.
**Decision/learning:** Kept the existing `FamilyOverview` response and computed the additional presentation-only stats client-side: top income, top expense, top saver, member income/expense bars, and expense-share pie. The toggle now only reveals/hides deeper fields, latest movement, and charts; member cards always stay visible with role, age/status, transaction count, income, expense, and net.
**Why it matters:** Do not regress the toggle back to an all-or-nothing hide. The family page uses Recharts only in this client component; if bundle size becomes a concern, split the chart block dynamically instead of dropping the always-visible member basics.
**Verification:** `pnpm lint`, `pnpm type-check`, `pnpm format:check`, and `docker compose up -d --build frontend` passed.
**Reference:** `frontend/components/FamilyClient.tsx`.

### 2026-05-13 — Day 7 — Dashboard long lists capped with full-list dialogs

**Context:** The unified `İşlemler` screen could grow indefinitely because recent transactions, recurring payment rows, and recurring-impact bars rendered every item inline.
**Decision/learning:** Added preview caps in `DashboardClient`: first 5 transactions, first 4 recurring payment rows, and first 4 active recurring-impact bars stay inline. Overflow opens scrollable Radix dialogs (`Tüm işlemler`, `Tüm tekrarlayan ödemeler`, `Tüm aylık tekrar etkileri`) that preserve the same row controls for delete/toggle actions.
**Why it matters:** Keep operational pages height-bounded by default. If another dashboard list can grow from user data, prefer this preview + full-list dialog pattern instead of adding another unbounded inline stack.
**Verification:** `pnpm lint`, `pnpm type-check`, `pnpm format:check`, and `docker compose up -d --build frontend` passed.
**Reference:** `frontend/components/dashboard-client.tsx`.

### 2026-05-13 — Day 7 — Recurring payments separate past-instance and future-rule edits

**Context:** The recurring-payment list needed an explicit management action where the user can fix one past payment without changing the recurring schedule, or change every future payment by editing the subscription rule.
**Decision/learning:** Added a `Yönet` dialog to recurring-payment rows in `DashboardClient`. `Geçmiş tek ödeme` edits a selected transaction through the existing scoped `PATCH /api/transactions/{id}` endpoint; `Gelecektekilerin tümü` edits the subscription through scoped `PATCH /api/subscriptions/{id}`. No schema migration was added. Because `transactions` do not store `subscription_id`, candidate past payments are matched heuristically from same-user past expenses (`source='recurring'`, merchant/name similarity, or same amount) and fall back to recent expenses for that profile. Overflow copy now says `menüde gör` instead of `pop-up içinde aç`.
**Why it matters:** This is a UX/API reuse layer, not canonical recurring-instance tracking. If exact recurring occurrence history becomes required, update `master_plan.md` first and add a real transaction-to-subscription relationship instead of strengthening the heuristic silently.
**Verification:** `pnpm type-check`, `pnpm lint`, and `pnpm format:check` passed.
**Reference:** `frontend/components/dashboard-client.tsx`, `frontend/lib/types.ts`.

### 2026-05-13 — Day 7 — Income/expense details and editable dated rows

**Context:** The dashboard needed a separate deep-dive page for income/expense details, editable past/future-dated rows, income-vs-expense category separation, and richer recurring payment analysis.
**Decision/learning:** Bumped `master_plan.md` to v0.16 before coding. Added `/dashboard/income-expense` with Recharts pie/bar tooltips, editable transaction rows via the existing scoped transaction PATCH endpoint, and subscription click-through details showing heuristic paid history, total paid, and latest increase. Shared helpers now group system categories into income/expense options without changing the `categories` schema. Added migration `0004_income_categories` to seed missing system categories (`Harçlık`, `Staj`, `Hediye`, `Freelance`, `Faiz geliri`, `Diğer gelir`, `Yemek`, `Akaryakıt`, `Telekom`, `Ev`) and expanded demo seed with recurring/history rows so the detail page has meaningful data.
**Why it matters:** Category type is currently a frontend grouping over category names, not a DB column. If category type becomes user-editable or API-enforced, update the schema and master plan instead of relying on the UI helper. Subscription history remains heuristic until `transactions.subscription_id` or a separate occurrence table exists.
**Verification:** Focused backend tests (`uv run pytest tests/test_demo_seed.py tests/test_transactions.py tests/test_subscriptions.py -q`), backend `ruff`, backend `mypy`, frontend `pnpm type-check`, `pnpm lint`, and `pnpm format:check` passed.
**Reference:** `docs/master_plan.md` v0.16, `backend/alembic/versions/0004_income_expense_categories.py`, `backend/app/workers/demo_seed.py`, `frontend/components/IncomeExpenseClient.tsx`, `frontend/components/TransactionEditDialog.tsx`, `frontend/lib/category-groups.ts`, `frontend/lib/recurring-analysis.ts`.

### 2026-05-13 — Day 7 — Due recurring payments materialize on read paths

**Context:** Finished the v0.17 recurring-payment follow-up: active subscriptions should automatically become expense transactions when their billing day arrives, and dashboard/detail views should show the updated row without a separate scheduler in the demo path.
**Decision/learning:** `materialize_due_subscriptions` now runs before transaction list/summary reads and before subscription list reads. The subscription query uses `FOR UPDATE SKIP LOCKED` so concurrent dashboard requests do not race on the same due rows. Duplicate detection is keyed by the materializer metadata stored in `transactions.raw_ocr_data` (`subscription_id` + `billing_date`), not by merchant/date, because a user can have two distinct subscriptions from the same merchant on the same day. The materialized transaction is still a normal scoped `type='expense'`, `source='recurring'` transaction and `next_billing_date` is advanced through all missed periods.
**Why it matters:** Do not change the duplicate guard back to merchant/date matching; that silently drops same-merchant same-day subscriptions. This remains read-side materialization for hackathon/demo reliability, not a full scheduler/occurrence ledger. If exact recurring occurrence editing becomes required, update the master plan and add a real `subscription_id` relationship instead of overloading the heuristic.
**Verification:** `uv run pytest -q` (64 tests), `uv run ruff check app tests`, `uv run mypy app`, `pnpm lint`, `pnpm type-check`, `pnpm format:check`, `pnpm build`, `git diff --check`, and container `docker compose exec -T backend uv run alembic upgrade head && docker compose exec -T backend uv run alembic check && docker compose exec -T backend uv run python -m app.workers.demo_seed` passed. `pnpm build` still prints the known Next.js flat-config plugin warning.
**Reference:** `docs/master_plan.md` v0.17 İK-18/§12.2.19, `backend/app/services/recurring_materializer.py`, `backend/app/routers/transactions.py`, `backend/app/routers/subscriptions.py`, `backend/tests/test_recurring_materializer.py`, `frontend/components/IncomeExpenseClient.tsx`.

### 2026-05-13 — Day 7 — Income/expense detail uses one shared date range

**Context:** The `/dashboard/income-expense` screen mixed current-month summaries/charts with an unfiltered dated transaction list, which made the visible records look disconnected from the totals.
**Decision/learning:** Added a ledger-style `Tarih aralığı` control with explicit `Başlangıç`/`Bitiş` inputs plus quick ranges (`Bu ay`, `Geçen ay`, `Son 3 ay`, `Tüm kayıtlar`). The selected range is applied consistently to the selected income/expense total, category pie, dated record list, monthly breakdown, and recurring-payment history. The date comparison uses Europe/Istanbul day keys so UI filtering follows the project date invariant instead of the browser's arbitrary timezone.
**Why it matters:** Keep this page range-driven from one state object; do not reintroduce separate chart/list filters unless there is a clear UX reason. API still returns the latest 100 scoped transactions, so very old custom ranges may require backend pagination later if production data grows beyond demo scale.
**Verification:** `pnpm lint`, `pnpm type-check`, `pnpm format:check`, `pnpm build`, and `git diff --check` passed. `pnpm build` still prints the known Next.js flat-config plugin warning.
**Reference:** `frontend/components/IncomeExpenseClient.tsx`, `docs/master_plan.md` v0.16 §12.2.18.

### 2026-05-13 — Day 7 — Transaction lists use compact receipt rows

**Context:** The `/dashboard/transactions` page felt oversized after adding management actions and full-list dialogs; transaction and recurring-payment rows consumed too much vertical space.
**Decision/learning:** Kept the household-ledger/receipt visual language but tightened the data rows: smaller row padding, reduced heading/amount type size, shorter action buttons, tighter list gaps, smaller recurring-impact bars, and more compact section headers. The input form remains readable, while the right-side operational lists now behave more like dense finance tables.
**Why it matters:** For data-heavy finance surfaces, prefer compact receipt rows over large card rows. Keep large display typography for summary/hero moments, not every transaction line.
**Verification:** `pnpm lint`, `pnpm type-check`, `pnpm format:check`, `pnpm build`, and `git diff --check` passed.
**Reference:** `frontend/components/dashboard-client.tsx`.

### 2026-05-13 — Day 7 — Chat messages render lightweight Markdown emphasis

**Context:** Assistant replies could include Markdown-style text like `**başlık**`, but the chat UI rendered the asterisks literally and long assistant replies felt narrow on wide screens.
**Decision/learning:** Added a small safe formatter for chat text instead of introducing a Markdown dependency. It supports bold emphasis and simple bullet lines, and is reused by live chat and chat history. Assistant bubbles now get wider max widths and more internal spacing at large breakpoints, while user bubbles stay compact.
**Why it matters:** Keep chat formatting intentionally small and safe; do not render raw HTML from model output. If richer Markdown is needed later, add a sanitized renderer deliberately and test historical messages too.
**Verification:** `pnpm lint`, `pnpm type-check`, `pnpm format:check`, `pnpm build`, and `git diff --check` passed.
**Reference:** `frontend/components/ChatMessage.tsx`, `frontend/components/ChatStream.tsx`, `frontend/components/ChatHistoryClient.tsx`.

### 2026-05-13 — Day 7 — Chat monthly trend charts use flat series points

**Context:** Implemented the v0.18 chat request for questions like “Market harcamam ay ay nasıl değişti?” and “Netflix aboneliğim her ay nasıl değişti?”.
**Decision/learning:** `visualize_spending` now accepts `chart_type="monthly"` and optional `category`/`target`/`targets`/`target_type`/`query` hints. The backend still uses scoped `transactions` with `visible_user_ids`; monthly buckets are Europe/Istanbul local months and amounts stay decimal strings. Monthly chart data is a flat point list (`label`, `series`, `value`, `value_formatted`), and the frontend groups those points into Recharts bars. Inference prefers explicit category-name matches before merchant matches unless the prompt contains abonelik/tekrarlayan/satıcı wording, so “Market ay ay” stays a category trend while “Netflix aboneliğim ay ay” becomes a vendor/subscription trend.
**Why it matters:** Do not change monthly chart payloads to dynamic per-series keys at the API boundary; historical chat attachments depend on the flat shape being parseable. Subscription/vendor matching remains heuristic because transactions have no canonical `subscription_id` column, except recurring materializer metadata when present.
**Verification:** `uv run pytest tests/test_agent_tools.py tests/test_chat_stream.py tests/test_conversations.py -q`, `uv run pytest -q`, `uv run ruff check app tests`, `uv run ruff format --check app tests`, `uv run mypy app`, `pnpm lint`, `pnpm type-check`, `pnpm format:check`, `pnpm build`, and `git diff --check` passed. `pnpm build` still prints the known Next.js flat-config plugin warning.
**Reference:** `docs/master_plan.md` v0.18 §12.2.14/§16, `backend/app/agent/tools.py`, `backend/app/services/agent_runner.py`, `frontend/components/ChatChart.tsx`, `frontend/lib/chat-attachments.ts`, `frontend/lib/types.ts`.

### 2026-05-14 — Day 7 — Dashboard pie hover and investment refusal guard

**Context:** Added a more interactive dashboard category pie and tightened agent behavior for investment-advice prompts.
**Decision/learning:** The main dashboard expense pie now gently rocks while idle and pauses/reveals category detail rows on hover or keyboard focus; touch/coarse-pointer devices keep details visible so mobile users are not blocked by hover-only UI. The stable system prompt now explicitly says the agent must never provide investment advice, and the deterministic stream path rejects obvious investment-advice requests before live LLM routing so the rule works even without provider keys.
**Why it matters:** Keep the pie interaction hover-enhanced, not hover-dependent. Investment refusal should stay outside tool routing; do not let “hangi hisse/fon/kripto alınır?” fall through to spending or scenario tools.
**Verification:** `uv run pytest tests/test_chat_stream.py -q`, `uv run pytest -q`, `uv run ruff check app tests`, `uv run ruff format --check app tests`, `uv run mypy app`, `pnpm lint`, `pnpm type-check`, `pnpm format:check`, `pnpm build`, and `git diff --check` passed. `pnpm build` still prints the known Next.js flat-config plugin warning.
**Reference:** `frontend/components/SpendingChart.tsx`, `frontend/app/globals.css`, `backend/app/agent/prompts.py`, `backend/app/services/agent_runner.py`, `backend/tests/test_chat_stream.py`.

### 2026-05-13 — Day 7 — Zarf budget dashboard and agent answers

**Context:** Added Semih's requested Turkish family budget envelope metaphor to the dashboard and spending answers.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.16 after rebasing onto the latest `origin/day-1-bootstrap` v0.15 work. The implementation deliberately reuses `categories.budget_monthly` as the envelope budget/goal source instead of adding a savings-goal table. `backend/app/services/envelopes.py` centralizes the six MVP envelopes (`Market`, `Fatura`, `Okul`/`Eğitim`, `Ulaşım`, `Harçlık`, `Birikim`) so `/api/transactions/summary` and `get_spending` return consistent scoped values. Demo seed creates Ayşe-owned category budgets, and agent fallback answers now say things like "Market zarfında bu ay 420,00 ₺ kaldı" plus safe daily spend when a budget exists. `Birikim` is excluded from risky-category selection because progress there is positive, not overspending.
**Why it matters:** Keep long-term/multi-period savings goals in stretch scope; the MVP `Birikim zarfı` is only a monthly target. If future UI lets users edit budgets, write to user-owned categories and keep the envelope helper as the single mapping point so `Okul zarfı` continues to map to `Eğitim`.
**Verification:** `uv run ruff check app tests && uv run ruff format --check . && uv run mypy app && uv run pytest -q` passed with 60 tests. `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 type-check`, and `npx pnpm@11.0.9 format:check` passed.
**Reference:** `docs/master_plan.md` v0.16, `backend/app/services/envelopes.py`, `backend/app/routers/transactions.py`, `backend/app/agent/tools.py`, `backend/app/services/agent_runner.py`, `frontend/components/dashboard-client.tsx`.

### 2026-05-13 — Day 7 — Expense-reduction goals scoped as MVP

**Context:** Teammate proposed adding something beyond the monthly `Birikim zarfı`: a goal where the user reduces spending in a specific category month by month, with agent-created goals and tactics.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.17 and scoped the feature to category-based expense-reduction goals only. This deliberately does not implement long-term accumulation/birikim goals yet; those remain stretch because the zarf MVP already covers monthly savings. The new model stores baseline spend, target spend, expected saving, date range, strategy JSON, and whether the goal was created by the user or agent.
**Why it matters:** Keep the first implementation narrow: `create_saving_goal` and `get_saving_goal_progress` are enough for a demo. Do not use floats in tool inputs or persistence; convert reduction percentages and money through `Decimal` and compute progress from scoped transaction rows.
**Verification:** `uv run ruff check app tests && uv run ruff format --check . && uv run mypy app && uv run pytest -q` passed with 67 tests. `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 type-check`, and `npx pnpm@11.0.9 format:check` passed.
**Reference:** `docs/master_plan.md` v0.17, `backend/app/models/saving_goal.py`, `backend/app/services/saving_goals.py`, `frontend/components/SavingGoalsClient.tsx`.

### 2026-05-13 — Day 7 — Smart goal plan stays tool-based

**Context:** Teammate proposed richer goal planning, AI finance lessons, voice, and video generation. The strongest demo path is the user saying they want a vacation and need to reduce expenses.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.18 and added `Akıllı hedef planı` as a narrow agent workflow. It reuses spending/subscription data and the existing category saving-goal table; it does not add video generation, real-time voice, or investment advice. Finance lessons stay covered by `explain_concept`/`illustrate_concept` for now.
**Why it matters:** Keep this as an action-oriented demo: intent → scoped data lookup → 1–2 category reduction goals → tactics. Do not add a broader course platform or voice stack unless the plan changes again.
**Verification:** `uv run ruff check app tests && uv run ruff format --check . && uv run mypy app && uv run pytest -q` passed with 69 tests. `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 type-check`, and `npx pnpm@11.0.9 format:check` passed.
**Reference:** `docs/master_plan.md` v0.18, `backend/app/services/smart_plans.py`, `backend/app/agent/tools.py`.

### 2026-05-13 — Day 7 — Finance school uses existing chat tools

**Context:** Teammate suggested ready-made AI financial lessons, voice, and video. The safe subset is a controlled lesson list that can be read or narrated without building a full course platform.
**Decision/learning:** Bumped `docs/master_plan.md` to v0.19 and scoped `Finans Okulu` as frontend orchestration over the existing chat stream. Lesson topics call `explain_concept`, optional visual mode can trigger `illustrate_concept`, and browser text-to-speech can read the generated answer. No new backend table or video generation is needed.
**Why it matters:** Keep lesson topics predefined so investment-sensitive content like money market funds stays educational. Do not add product recommendations or market timing; prompt text still says no al/sat/tut advice.
**Verification:** `uv run ruff check app tests && uv run ruff format --check . && uv run mypy app && uv run pytest -q` passed with 69 tests. `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 type-check`, and `npx pnpm@11.0.9 format:check` passed.
**Reference:** `docs/master_plan.md` v0.19, `frontend/components/FinancialLessonsClient.tsx`, `frontend/app/(app)/learn/page.tsx`.

### 2026-05-14 — Integration — day-1-bootstrap + zarf-budget-goals merge

**Context:** `integration/merge-features` was created from `origin/day-1-bootstrap` and merged with `origin/semih/zarf-budget-goals`.
**Decision/learning:** Conflict resolution kept both feature lines: Day 7 income/expense detail, recurring materialization, monthly trend charting, dashboard pie hover/investment refusal, plus zarf budget, saving goals, smart goal plans, and Finance School. `docs/master_plan.md` is now v0.20 and §12.2 is renumbered instead of dropping either branch's scope. The saving-goals Alembic revision was linearized after `0004_income_categories` as `0005_saving_goals` to avoid multiple heads.
**Why it matters:** Future work should treat the integrated dashboard summary as both budget-aware and recurring-aware. Do not remove `materialize_due_subscriptions` from transaction read paths when extending envelope summaries, and do not route investment advice into saving-goal or lesson tools.
**Reference:** `docs/master_plan.md` v0.20, `backend/alembic/versions/0005_saving_goals.py`, `frontend/components/dashboard-client.tsx`, `backend/app/agent/tools.py`, `backend/app/services/agent_runner.py`.

### 2026-05-14 — Integration — Finance School advice guard false positives

**Context:** Clicking Finance School lessons could return the investment-advice refusal because the lesson prompt said "Yatırım tavsiyesi verme" and "günlük hayattan" could combine with "eğitim amaçlı" to look like an `Eğitim` envelope query.
**Decision/learning:** The deterministic investment guard now matches direct advice intent with regex patterns instead of treating every "yatırım tavsiyesi" occurrence as a request. Finance School prompts avoid advice-action wording, and `günlük` is no longer a standalone envelope-budget hint because lesson copy uses it as an everyday-life phrasing.
**Why it matters:** Keep educational safety instructions and investment advice requests separate: "tavsiye verme" should not be refused, but "hangi fon alınır?" still must be refused before tools or live LLM routing.
**Verification:** `uv run pytest tests/test_chat_stream.py -q`, `uv run pytest -q`, `uv run ruff check app tests`, `uv run ruff format --check app tests`, `uv run mypy app`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 format:check`, `npx pnpm@11.0.9 build`, `git diff --check`, `docker compose up -d --build`, API smoke for the Finance School faiz prompt, and API smoke for "Hangi fon alınır?" passed.
**Reference:** `backend/app/services/agent_runner.py`, `frontend/components/FinancialLessonsClient.tsx`, `backend/tests/test_chat_stream.py`.

### 2026-05-14 — Integration — Finance School routes lessons into chat

**Context:** Inline Finance School answers made `/learn` grow vertically and duplicated chat rendering behavior, so streamed Markdown like `###`, `**bold**`, `*italic*`, numbered lists, dividers, and image markdown could appear raw.
**Decision/learning:** `/learn` now only selects a controlled lesson and stores a one-shot pending chat message in session storage before navigating to `/chat`. `ChatStream` consumes that pending lesson once, starts a fresh conversation, and uses the normal chat stream, tool trace, image attachment, and message history path. `ChatMessage` is the shared lightweight Markdown renderer and now handles headings, ordered lists, italic/bold emphasis, dividers, Markdown image lines, and assistant text-to-speech.
**Why it matters:** Keep lesson answer rendering centralized in chat. Do not reintroduce a second streamed answer panel in `FinancialLessonsClient`; it will drift from chat formatting and make the learn page height unbounded again.
**Verification:** `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, `npx pnpm@11.0.9 build`, `git diff --check`, `docker compose up -d --build frontend`, `GET /learn`, `GET /chat`, and backend health check passed. Browser click automation was not run because no browser tool was exposed and Playwright is not installed in the project.
**Reference:** `frontend/components/FinancialLessonsClient.tsx`, `frontend/components/ChatStream.tsx`, `frontend/components/ChatMessage.tsx`, `frontend/lib/chat-session.ts`.

### 2026-05-14 — Day 7 — Unified smart goals and actionable learning/dashboard paths

**Context:** Continued Semih's zarf/goal work after the integration branch landed, adding real `Birikim hedefi` support alongside existing category-reduction goals.
**Decision/learning:** Bumped `master_plan.md` to v0.21 before coding because multi-period accumulation moved out of stretch scope. Reused `saving_goals` instead of creating a separate table: `goal_type='expense_reduction'|'accumulation'`, optional `target_amount`, `current_amount`, and `monthly_contribution` distinguish the two goal modes while existing reduction fields remain backward-compatible. Added `create_accumulation_goal`, deterministic chat routing for amount-based birikim prompts, and smart-plan creation of an accumulation goal when the user provides a target amount. Frontend `/dashboard/goals` is now `Akıllı hedefler` with Birikim/Tasarruf modes, `/learn` groups predefined lessons by level and stores local progress, and dashboard coach notes expose direct actions for goal creation, lessons, and smart-plan chat handoff. A second review fixed accumulation progress to measure from the starting amount toward the target, prevented controlled Turkish amount inputs from double-formatting typed values, and made smart-plan replies mention a created birikim goal even when there is not enough spending data for category-reduction goals.
**Why it matters:** Treat accumulation goals as budget-planning targets, not investment advice or automatic contribution tracking. The table still does not link savings contributions to transactions; if exact contribution matching becomes necessary, update the plan first and add a deliberate ledger relationship. Lesson rendering must stay centralized in chat; localStorage progress is only a UI convenience.
**Verification:** `uv run ruff check app tests`, `uv run ruff format --check .`, `uv run mypy app`, `uv run pytest -q` (82 passed), `uv run alembic upgrade 0005_saving_goals:0006_accumulation_goals --sql`, `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, and `git diff --check` passed.
**Reference:** `docs/master_plan.md` v0.21, `backend/alembic/versions/0006_accumulation_goals.py`, `backend/app/services/saving_goals.py`, `backend/app/agent/tools.py`, `frontend/components/SavingGoalsClient.tsx`, `frontend/components/FinancialLessonsClient.tsx`, `frontend/components/dashboard-client.tsx`.

### 2026-05-15 — Day 7 — Goal chat visualization and clickable details

**Context:** A teammate clarified that birikim/tasarruf goals should not only be creatable from chat; the agent should also list current goals, show them with the same inline chart mechanism as spending graphs, and let users click a goal card for details.
**Decision/learning:** Bumped `master_plan.md` to v0.22 and added two scoped tools instead of overloading spending visualization: `get_saving_goals` returns active goal progress rows, while `visualize_saving_goals` returns a `chart` payload compatible with the existing `ChatChart` extraction path. The deterministic runner now emits both tool calls for “hedeflerimi göster/grafikle göster” before generic spending visualization, so API-key-free demos still show goal summaries and charts. `/dashboard/goals` keeps one page but makes cards selectable; the detail panel shows progress, a small two-bar comparison, dates, remaining amount/limit, and saved tactics.
**Why it matters:** Goal charts are about progress percentage, not investment performance or product returns. Keep this separate from `visualize_spending`; otherwise “hedeflerimi grafikle göster” can accidentally become a spending-category chart and miss the teammate’s requested demo flow.
**Verification:** `uv run pytest tests/test_agent_tools.py tests/test_chat_stream.py -q` passed with 32 tests, `uv run pytest -q` passed with 84 tests, `uv run ruff check app tests`, `uv run ruff format --check .`, `uv run mypy app`, `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, and `git diff --check` passed.
**Reference:** `docs/master_plan.md` v0.22, `backend/app/agent/tools.py`, `backend/app/services/agent_runner.py`, `backend/tests/test_agent_tools.py`, `backend/tests/test_chat_stream.py`, `frontend/components/SavingGoalsClient.tsx`, `frontend/components/ChatStream.tsx`.

### 2026-05-15 — Day 7 — Goal management actions stay manual

**Context:** Added management actions for the unified smart-goals screen after users could create, list, visualize, and inspect goals.
**Decision/learning:** Bumped `master_plan.md` to v0.23 and added scoped `PATCH /api/saving-goals/{goal_id}` for status changes plus accumulation-only manual contribution updates. Contributions update `saving_goals.current_amount`, refresh the remaining/tactic strategy fields, and auto-complete only when the current amount reaches the target; they deliberately do not create `transactions` rows and are rejected for inactive goals. The frontend now loads all goal statuses, shows `Duraklat`/`Sürdür`, `Tamamlandı`, less-prominent `Sil`, active-only `Katkı ekle`, and uses the existing pending-chat handoff for `Koçtan plan iste`.
**Why it matters:** Do not infer or materialize savings contributions into the ledger without a future schema decision; current goal progress is manual state plus scoped transaction-derived spending for reduction goals. If resume/history/audit becomes required, update the plan before adding a goal action ledger.
**Verification:** `uv run pytest tests/test_saving_goals.py -q`, `uv run ruff check app tests`, `uv run ruff format --check .`, `uv run mypy app`, `uv run pytest -q` (90 passed), `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, and `git diff --check` passed.
**Reference:** `docs/master_plan.md` v0.23, `backend/app/routers/saving_goals.py`, `backend/app/services/saving_goals.py`, `frontend/components/SavingGoalsClient.tsx`, `frontend/lib/chat-session.ts`.

### 2026-05-16 — Ops — Docker commands need elevated agent shell access

**Context:** Rebuilt and relaunched the local Docker stack from the agent shell.
**Decision/learning:** Docker Desktop itself was running, but sandboxed `docker` calls could not read `~/.docker/config.json` or connect to the `docker_engine` pipe. Running Docker CLI commands in the elevated shell context worked immediately; `docker compose up -d --build` rebuilt the stack and `docker compose exec backend uv run alembic upgrade head` advanced the DB from `0005_saving_goals` to `0006_accumulation_goals`.
**Why it matters:** If a future agent sees Docker “permission denied” or missing-pipe errors from the sandbox, first retry the Docker command with elevated permissions before assuming the daemon is down or changing repo config.
**Verification:** `docker version`, `docker compose up -d --build`, `docker compose exec backend uv run alembic upgrade head`, `docker compose ps`, `GET http://localhost:8000/health`, and `GET http://localhost:3000/login` passed.
**Reference:** `SETUP.md`, `docker-compose.yml`.

### 2026-05-16 — Demo data — Goal and memory fixtures follow real seeded spend

**Context:** Filled the post-Day-7 demo gaps so Ayşe and Mehmet open with both accumulation and expense-reduction goals plus visible memory entries.
**Decision/learning:** `backend/app/workers/demo_seed.py` now seeds four active goals (`Yaz tatili birikimi`, `Market harcamamı azalt`, `Acil durum fonu`, `Eğlence harcamamı azalt`) and four example `agent_memory` rows for Ayşe/Mehmet. Expense-reduction goal seeding chooses the same-named category record that actually has recent expense rows, because older local demo DBs can still have transactions on system categories while newer runs also have Ayşe-owned envelope categories with the same label.
**Why it matters:** When extending demo data, do not assume a user-owned shadow category is the one historical transactions use. Tie derived fixtures to the records that contain the live scoped data, or local re-seeds can look valid in code but fail against existing demo volumes.
**Verification:** `uv run pytest tests/test_demo_seed.py -q`, `uv run pytest -q`, `uv run ruff check app tests`, `uv run ruff format --check app tests`, `docker compose exec -T backend uv run python -m app.workers.demo_seed`, and direct Postgres checks for 4 demo saving goals plus 4 demo memory rows passed.
**Reference:** `backend/app/workers/demo_seed.py`, `backend/tests/test_demo_seed.py`, `docs/master_plan.md` v0.23 §12.2.21 and İK-9.

### 2026-05-16 — Day 7 — Goal list cards stay compact

**Context:** The unified goals page became visually uneven because accumulation mode used a taller creation form than expense-reduction mode, and the summary cards repeated the same tactic list that already exists in the detail panel.
**Decision/learning:** `SavingGoalsClient` now top-aligns the hero grid, uses two-column form layouts for both goal modes on wider screens, tightens the page/card spacing, and keeps tactics in the detail panel instead of repeating them inside every summary card.
**Why it matters:** The list view should stay scannable while the detail panel carries the richer explanation. If tactic content is duplicated in both places, accumulation and reduction screens drift in height and the goals page starts feeling heavier than the rest of the dashboard.
**Verification:** `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 format:check`, and `docker compose up -d --build frontend` passed.
**Reference:** `frontend/components/SavingGoalsClient.tsx`.

### 2026-05-16 — Day 7 — Finance School expands by level, not by random topics

**Context:** The first Finans Okulu pass proved the flow, but the catalog still felt thin: child lessons were especially sparse and intermediate/advanced paths ended quickly.
**Decision/learning:** Expanded the predefined lesson catalog inside `FinancialLessonsClient` with additional child, beginner, intermediate, and advanced topics while keeping the same controlled-chat workflow. The new topics cover ihtiyaç/istek, harçlık planlama, gelir-gider, acil durum fonu, abonelik takibi, ekstre okuma, bileşik faiz, and çeşitlendirme. The default selected lesson now matches the beginner tab shown on first load.
**Why it matters:** Finans Okulu should feel like a short curriculum rather than a demo menu. Keep expanding it through curated level-based topics; do not turn it into an open-ended investment prompt surface or duplicate the chat renderer on `/learn`.
**Verification:** `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 type-check`, and `npx pnpm@11.0.9 format:check` passed.
**Reference:** `frontend/components/FinancialLessonsClient.tsx`, `docs/master_plan.md` v0.23 §12.2.23.

### 2026-05-16 — Day 7 — Finance School progress tracks starts, not completions

**Context:** The Learn page had a persistent `Seçili ders` sidebar that could keep showing the default lesson after users switched level tabs, and its progress UI visually implied completion even though the only reliable local event is starting a lesson.
**Decision/learning:** Removed the sidebar and let the lesson cards remain the only launch surface. Renamed the persisted UI semantics from completed lessons to started lessons, show `x/y ders başlatıldı`, and show `Tüm dersler başlatıldı.` once there is no unstarted lesson left.
**Why it matters:** Do not present local lesson launches as confirmed completion. Real completion tracking would need an explicit completion action or a reliable chat-side completion signal; until then, the truthful metric is which predefined lessons have been started.
**Verification:** `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 type-check`, and `npx pnpm@11.0.9 format:check` passed.
**Reference:** `frontend/components/FinancialLessonsClient.tsx`.

### 2026-05-16 — Day 7 — Receipt entry merged into transactions

**Context:** The app had separate manual/recurring entry and receipt upload surfaces, while the demo flow needed all data entry in one place.
**Decision/learning:** `/dashboard/transactions` now includes receipt scanning/confirmation via `ReceiptUploader`, `/receipts` redirects to the transactions screen, receipt-related insight actions point to transactions, and the sidebar no longer exposes a separate receipt nav item. `ReceiptUploader` gained `showHistory` and `onConfirmed` props so the combined screen can refresh its transaction list without duplicating receipt history.
**Why it matters:** Keep data-entry UX centered on the transactions page. If a future standalone receipt archive is reintroduced, preserve the confirmation callback and avoid creating a second source of truth for transaction state.
**Verification:** `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, `npx pnpm@11.0.9 build`, and `uv run pytest tests/test_agent_tools.py tests/test_chat_stream.py tests/test_saving_goals.py -q` passed. Added `.tmp-chrome-profile` to ignore files after Prettier tried to scan local browser-profile artifacts.
**Reference:** `frontend/components/dashboard-client.tsx`, `frontend/components/ReceiptUploader.tsx`, `frontend/app/(app)/receipts/page.tsx`, `frontend/components/sidebar.tsx`.

### 2026-05-16 — Day 7 — Custom lessons stay transient and scope guard is deterministic

**Context:** Finished the Finans Okulu custom lesson follow-up from `master_plan.md` v0.24 and tightened the prompt-injection path found during smoke testing.
**Decision/learning:** `create_custom_lesson` remains a chat/tool result only; no lesson table or separate endpoint was added. The deterministic chat runner now handles custom lesson prompts before live LLM routing, optionally chains `illustrate_concept`, and refuses data requests that try to change scope with a raw UUID, `user_id`, or a possessive third-person name such as `Kerem'in ...`. Category possessives are allowed by checking the visible category names, so `Market'in ...` does not become a privacy false positive.
**Why it matters:** Future Finance School work should keep answer rendering centralized in chat and avoid persisting generated lessons unless the master plan changes again. Scope guards must stay outside the LLM path so API-key-free demos and live-provider demos both enforce İK-7/İK-8 before any data tool runs.
**Verification:** `uv run pytest -q` passed with 96 tests. `uv run ruff check app tests`, `uv run ruff format --check .`, `uv run mypy app`, `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, `npx pnpm@11.0.9 build`, and `git diff --check` passed. `next build` still prints the known Next.js flat-config plugin warning.
**Reference:** `docs/master_plan.md` v0.24 §12.2.23, `backend/app/agent/tools.py`, `backend/app/services/agent_runner.py`, `backend/tests/test_agent_tools.py`, `backend/tests/test_chat_stream.py`, `backend/tests/test_agent_graph.py`, `frontend/components/FinancialLessonsClient.tsx`.

### 2026-05-16 — Day 7 — Family cards and entry form progressive disclosure

**Context:** Tightened the family and transaction-entry screens after manual UI review: active child state did not update on the family page after returning to parent from the top banner, child cards were too tall, and category creation was split from the category field.
**Decision/learning:** `FamilyClient` now listens for the same `ACTIVE_PROFILE_EVENT` as the app shell, so returning to the parent profile immediately clears the child-card active state without a refresh. Child profile rows are compact; birth date, name, finance language, and the destructive `Aileden kaldır` action moved into a dialog. Backend gained parent-scoped `DELETE /api/family/children/{child_id}` and relies on the existing user FK cascade for child-owned data. The transaction screen removed the separate `Yeni kategori` box: category is now one datalist-backed field that accepts existing names or creates a new category during save. Merchant/source inputs use datalist suggestions from previously entered transaction and subscription merchants.
**Why it matters:** Keep family rows scannable and put rarely used edits behind progressive disclosure. There is still no `users.is_active`/soft-delete schema, so UI copy says `Aileden kaldır`; adding true deactivation would require a master-plan/schema decision. Do not reintroduce a separate category-create panel unless the one-field flow proves insufficient.
**Verification:** `uv run pytest -q` passed with 97 tests. `uv run ruff check app tests`, `uv run ruff format --check .`, `uv run mypy app`, `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, `npx pnpm@11.0.9 build`, and `git diff --check` passed. `next build` still prints the known Next.js flat-config plugin warning.
**Reference:** `backend/app/routers/family.py`, `backend/tests/test_family.py`, `frontend/components/FamilyClient.tsx`, `frontend/components/dashboard-client.tsx`, `frontend/lib/active-profile.ts`.

### 2026-05-16 — Day 7 — Low-risk demo polish stays frontend-only

**Context:** Continued the final sprint roadmap after Phase 1 UI polish, while explicitly skipping the P0 submission package for later.
**Decision/learning:** Bumped `master_plan.md` to v0.25 only for the Web Speech chat surface. Added Turkish cultural accumulation-goal templates, milestone celebration toasts, an adult dashboard month-end projection card, and optional chat voice input/read-aloud without adding backend endpoints, schema changes, or new dependencies. The related-goal spending list now filters by both `goal.user_id` and `category_id`, so parent family views do not mix another family member's same-category transactions into a selected goal.
**Why it matters:** Keep these differentiators as UI orchestration over existing scoped endpoints. Browser speech recognition is conditional; unsupported browsers simply keep text chat. Larger notification-center and memory-write work still needs a separate master-plan/scope pass and sensitive-data tests before implementation.
**Verification:** `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, `npx pnpm@11.0.9 build`, and `git diff --check` passed.
**Reference:** `docs/master_plan.md` v0.25, `frontend/components/ChatStream.tsx`, `frontend/components/SavingGoalsClient.tsx`, `frontend/components/dashboard-client.tsx`.

### 2026-05-16 — Day 7 — Notification center reuses scoped insights

**Context:** Added the first notification-center surface requested for final demo polish.
**Decision/learning:** Bumped `master_plan.md` to v0.26 and kept the notification center frontend-only: the sidebar bell fetches existing scoped `/api/insights`, counts non-dismissed rows, shows the latest coach notes in a dropdown, refreshes after active profile changes, and dismisses via the existing `PATCH /api/insights/{id}/dismiss` endpoint. It deliberately does not add browser push, a service worker, new insight types, backend generation, or memory writes.
**Why it matters:** Future notification work should start from backend insight generation, idempotency, and sensitive-data tests before adding new notification categories. Do not treat the bell as proof that background push or agent memory writes exist.
**Verification:** `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, `npx pnpm@11.0.9 build`, and `git diff --check` passed. `next build` still prints the known Next.js flat-config plugin warning.
**Reference:** `docs/master_plan.md` v0.26 §12.2.25, `frontend/components/NotificationBell.tsx`, `frontend/components/sidebar.tsx`, `backend/app/routers/insights.py`.

### 2026-05-16 — Day 7 — Insight refresh and memory writes are deterministic

**Context:** Follow-up self-review found that notification refresh could churn open insight rows, and chat memory still had read/delete but not explicit safe writes.
**Decision/learning:** Bumped `master_plan.md` to v0.27. `refresh_insights_for_user` now updates an existing open insight with the same `(user_id, insight_type, title)` instead of dismissing and recreating it, while stale open candidates are dismissed. Explicit chat phrases like `Bunu hatırla:` now route before the live LLM path into `remember_user_memory`, which writes only active-profile `agent_memory` rows and blocks API keys/tokens, passwords, IBANs, card numbers, TC identity numbers, raw OCR, base64-like payloads, and receipt-image wording.
**Why it matters:** The notification bell keeps stable IDs across refreshes, and memory writes are consent-based, scoped, deterministic, and protected before provider routing. Do not add automatic inference-based memory writes without a separate privacy review and tests.
**Verification:** `uv run pytest -q` passed with 104 tests. `uv run ruff check app tests`, `uv run ruff format --check app tests`, `uv run mypy app`, `npx pnpm@11.0.9 type-check`, `npx pnpm@11.0.9 lint`, `npx pnpm@11.0.9 format:check`, `npx pnpm@11.0.9 build`, and `git diff --check` passed. `next build` still prints the known Next.js flat-config plugin warning.
**Reference:** `docs/master_plan.md` v0.27 §12.2.25-26, `backend/app/services/insights.py`, `backend/app/agent/tools.py`, `backend/app/services/agent_runner.py`, `backend/tests/test_insights.py`, `backend/tests/test_agent_tools.py`, `backend/tests/test_chat_stream.py`.
