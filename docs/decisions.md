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
