# WORKDIVISION.md — Cüzdan Koçu, Days 2-7

> **Source plan:** [`docs/master_plan.md`](docs/master_plan.md) §18 is the day-by-day baseline; this document fleshes it out with **file-level ownership** so Person A and Person B can work in parallel without merge conflicts.

## Conventions

- **Person A (PA)** — backend-leaning lead. Owns `backend/app/agent/`, `backend/app/services/`, `backend/app/workers/`, agent prompts, deploy.
- **Person B (PB)** — frontend-leaning lead. Owns `frontend/app/`, `frontend/components/`, `frontend/lib/`, demo seeder visuals.
- Both are full-stack — when one's scope spills into the other's territory it's annotated.
- "Files touched" lists the **only** files each person should modify that day. If you need to touch a file outside your list, ping the other person on Discord first.
- "Handoff" lines describe artefacts (endpoints, types, env vars) that block the other person; we agree on **interface shape first** and merge it before either side codes the dependent half.
- Each day ends with a **21:00 sync** (master plan §18) and the day's checklist must be green before going to bed.

---

## Day 2 — 12 May Sal — Auth + transactions CRUD + Gemini hello-world

### Person A — backend foundations

**Goal:** Real auth endpoints + first transaction CRUD + first successful Gemini call.

Files touched:
- `backend/app/routers/auth.py` — `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `backend/app/routers/transactions.py` — `GET/POST/PATCH/DELETE /api/transactions`
- `backend/app/schemas/auth.py` (new) — `RegisterIn`, `LoginIn`, `UserOut`, `TokenOut` Pydantic models
- `backend/app/schemas/transaction.py` (new) — `TransactionIn`, `TransactionOut`, `TransactionFilter`
- `backend/app/schemas/__init__.py` (new)
- `backend/app/services/gemini.py` — minimal client + `ping()` smoke method (no LangGraph yet)
- `backend/tests/test_auth.py` (new) — register/login/me happy + invalid token paths
- `backend/tests/test_transactions.py` (new) — CRUD + user_id filter (İK-4 enforced)
- `backend/pyproject.toml` — add `langchain-google-genai`, `langchain-core`

**Handoff to PB by 17:00:**
- API contract for auth + transactions agreed in this PR (Pydantic schemas committed). PB reads `backend/app/schemas/*.py` to generate her TS types.
- `.env.example` already has `GEMINI_API_KEY` and `JWT_SECRET`; PA confirms a working `GEMINI_API_KEY` lives in his local `.env` and runs `python -m app.services.gemini` once to confirm.

**Daily risk:** Gemini API key not provisioned, or Türkiye IP rate-limited. **Mitigation:** PA creates the key first thing in the morning; if blocked, PA documents the OpenRouter proxy fallback in master plan §22.

### Person B — auth UX + transaction list UI + chat skeleton

**Goal:** Working login flow via NextAuth session carrier, dashboard reads transactions, chat sends a hard-coded mock reply.

Files touched:
- `frontend/app/(auth)/login/page.tsx` — convert to client component, wire submit to `signIn("credentials")`
- `frontend/app/(auth)/register/page.tsx` (new)
- `frontend/app/api/auth/[...nextauth]/route.ts` (new) — NextAuth Credentials provider; calls FastAPI `/api/auth/login`
- `frontend/lib/auth.ts` (new) — NextAuth config, JWT/session callbacks, backend token passthrough
- `frontend/app/(app)/layout.tsx` — add server-side redirect to `/login` when no NextAuth session
- `frontend/app/(app)/dashboard/page.tsx` — render transactions list (calls `GET /api/transactions`)
- `frontend/app/(app)/chat/page.tsx` — split into `<ChatStream/>` client component scaffold (no real streaming yet)
- `frontend/components/ChatStream.tsx` (new) — input + message list, calls placeholder `/api/chat/stream` (returns mock JSON)
- `frontend/lib/api.ts` — accept/use backend JWT from NextAuth session instead of the Day 1 localStorage-only path
- `frontend/lib/types.ts` (new) — TS types mirroring backend Pydantic schemas
- `frontend/components/ui/textarea.tsx` (new shadcn) — for chat input
- `frontend/package.json` — add `next-auth`

**Handoff from PA by 17:00:**
- PB starts on UI shells with mock data at 09:00; switches to live API at 17:00 once PA's PR merges.

**Daily risk:** Auth interface mismatch between PA and PB. **Mitigation:** **First action of the day** — both jump on a 15-min call to lock auth & transaction Pydantic shapes; PA commits empty schemas first, PB depends on those shapes from minute 1.

### End-of-day checklist (Day 2)

- [ ] `make migrate` runs cleanly on a fresh DB
- [ ] `curl -X POST /api/auth/register` and `/api/auth/login` return JWTs
- [ ] `curl /api/auth/me` with bearer token returns the user
- [ ] `curl /api/transactions` (with token) returns `[]` for new users
- [ ] Frontend login page redirects to `/dashboard` on success
- [ ] Both `make lint` and `make type-check` pass

---

## Day 3 — 13 May Çar — Agent tools + dashboard charts + chat ↔ backend

### Person A — first 3 agent tools + LangGraph wiring

**Goal:** Agent answers "Bu ay markete ne kadar?" using real DB data.

Files touched:
- `backend/app/agent/graph.py` — full LangGraph state machine (master plan §16)
- `backend/app/agent/tools.py` — implement `get_spending`, `get_subscriptions`, `get_user_memory` (per master plan §16 tool interfaces)
- `backend/app/agent/prompts.py` — `build_system_prompt(role, level)` (master plan §16)
- `backend/app/services/agent_runner.py` (new) — request-scoped invocation + streaming
- `backend/app/routers/chat.py` — `POST /api/chat/stream` SSE endpoint
- `backend/app/utils/tl_format.py` — implement `format_tl` (Day 1 left it `NotImplementedError`)
- `backend/app/utils/date_format.py` — implement `format_tr_date`
- `backend/tests/test_agent_tools.py` (new) — unit tests for each tool with İK-4 user_id filtering
- `backend/tests/test_utils.py` (new) — TL/date format

**Handoff to PB by 18:00:**
- SSE event format documented inline in `chat.py` docstring (event types: `message`, `tool_call`, `tool_result`, `done`).
- An example payload is checked in at `docs/agent_sse_example.json`.

**Daily risk:** LangGraph SSE backpressure with FastAPI's `StreamingResponse`. **Mitigation:** PA writes a 30-min spike at 09:00 with a fake echo agent before touching tools.

### Person B — dashboard charts + chat streaming

**Goal:** Recharts live, chat streams real responses.

Files touched:
- `frontend/app/(app)/dashboard/page.tsx` — add summary cards + spending chart
- `frontend/components/SpendingChart.tsx` (new) — Recharts pie/bar
- `frontend/components/InsightBanner.tsx` (new) — empty for Day 3, populated Day 6
- `frontend/components/ChatStream.tsx` — switch to real SSE consumption (`EventSource` or `fetch` ReadableStream)
- `frontend/components/ChatMessage.tsx` (new) — handles `assistant` / `user` / `tool` rendering, including agent trace
- `frontend/lib/sse.ts` (new) — typed SSE client matching PA's event format
- `frontend/package.json` — add `recharts`

**Handoff from PA by 18:00:**
- SSE happy path verified end-to-end via `curl --no-buffer` before PB starts wiring `EventSource`.

**Daily risk:** EventSource doesn't send Authorization headers; need fetch + ReadableStream OR cookies. **Mitigation:** PB picks fetch+ReadableStream upfront — no surprise mid-day.

### End-of-day checklist (Day 3)

- [ ] Chat sends "Bu ay markete ne kadar harcadım?", agent calls `get_spending`, response streams in Turkish
- [ ] Tool calls visible in chat as collapsible blocks (the "agentic trace" that scores §21)
- [ ] Dashboard renders Recharts with real DB numbers
- [ ] All amounts in UI render as `1.250,50 ₺`
- [ ] All dates render as `gg.aa.yyyy`
- [ ] `make test` green

---

## Day 4 — 14 May Per — Vision OCR + receipt upload UX

### Person A — `analyze_receipt` tool + MinIO

**Goal:** Upload a Migros receipt, agent returns a structured `Transaction`.

Files touched:
- `backend/app/services/minio.py` (new) — bucket bootstrap, presigned uploads
- `backend/app/services/ocr.py` — Gemini Vision call + structured JSON output
- `backend/app/agent/tools.py` — implement `analyze_receipt` (sixth slot per master plan §16)
- `backend/app/routers/receipts.py` — `POST /api/receipts/upload` (multipart) → URL + parsed candidate
- `backend/app/schemas/receipt.py` (new)
- `backend/tests/test_ocr.py` — uses 2-3 fixture images committed to `seeds/sample_receipts/`
- `seeds/sample_receipts/migros_*.jpg` (new fixtures)

**Handoff to PB by 17:00:** `POST /api/receipts/upload` working end-to-end with at least one real Türk receipt.

**Daily risk:** Gemini Vision parses Türk receipts poorly. **Mitigation:** master plan §22 Plan B → JSON fixture fallback; PA preps fixture data Day 4 morning.

### Person B — drag-drop receipt UX + confirmation flow

Files touched:
- `frontend/components/ReceiptUploader.tsx` (new) — drag-drop, preview, progress
- `frontend/app/(app)/receipts/page.tsx` — list previous receipts + uploader
- `frontend/components/ReceiptConfirmDialog.tsx` (new) — shows OCR result, lets user edit and confirm

**Handoff from PA:** schema for upload response (committed by 11:00).

### End-of-day checklist (Day 4)

- [ ] Drag a Migros JPG → OCR → confirmation → transaction shows in dashboard
- [ ] Receipt image visible in the receipts list
- [ ] MinIO bucket exists and is reachable

---

## Day 5 — 15 May Cum — Family mode + last 2 agent tools + demo seeder

### Person A — `explain_concept`, `simulate_scenario`, family filter

Files touched:
- `backend/app/agent/tools.py` — implement `explain_concept`, `simulate_scenario`
- `backend/app/agent/prompts.py` — child-mode prompt variant
- `backend/app/routers/family.py` — `GET /api/family`, `POST /api/family/children`, `POST /api/family/switch/:id`
- `backend/app/auth.py` — extend `get_current_user` with optional `family_switch` (parent acting as child)
- `seeds/demo_family.py` (new) — Yılmaz ailesi seeder per master plan §3.1
- `backend/tests/test_family.py` (new) — İK-4, İK-5 enforcement

### Person B — family UI + family switch + demo run

Files touched:
- `frontend/app/(app)/family/page.tsx` — list family members, add child form
- `frontend/components/FamilySwitch.tsx` (new) — dropdown on header
- `frontend/components/AgeAppropriateBadge.tsx` (new) — child-mode visual hint
- `frontend/app/(app)/chat/page.tsx` — child-mode visual styling

**Handoff:** `POST /api/family/switch/:id` returns a new JWT; PB stores it, switches local state.

### End-of-day checklist (Day 5)

- [ ] Run `python seeds/demo_family.py` — creates Ayşe + Mehmet + Elif
- [ ] Login as Ayşe, switch to Elif, ask "Faiz nedir?" → child-language answer
- [ ] Trying to access Elif's data without switching = 403

---

## Day 6 — 16 May Cmt — Proactive worker + Coolify deploy + UI polish

### Person A — proactive insights worker + production deploy

Files touched:
- `backend/app/workers/proactive.py` — APScheduler job, 4 rules (master plan §17)
- `backend/app/main.py` — start scheduler on app startup (only when `APP_ENV=production` or `RUN_SCHEDULER=true`)
- `backend/app/routers/insights.py` — `GET /api/insights`, `PATCH /api/insights/:id/dismiss`
- `backend/tests/test_proactive_worker.py` (new) — each rule fires under expected DB state, doesn't fire otherwise
- `coolify.yaml` (new, OR Coolify UI config) — deploy spec
- `docs/master_plan.md` — update §18 with deploy URL

**Daily risk:** Coolify hiccup. **Mitigation:** PA budgets 2h block at 14:00; if not green by 18:00, fall back to Vercel + Railway (master plan §22 Plan B).

### Person B — UI polish, dark mode pass, mobile

Files touched:
- `frontend/app/(app)/dashboard/page.tsx` — `<InsightBanner/>` wired
- `frontend/components/InsightBanner.tsx` — full implementation, severity colors, dismiss
- `frontend/app/globals.css` — refine dark mode contrast
- `frontend/components/sidebar.tsx` — mobile drawer (responsive breakpoints)
- All page files — mobile-first padding pass

### End-of-day checklist (Day 6)

- [ ] Live Coolify URL responds with valid HTTPS
- [ ] Demo Yılmaz family seeded on prod DB (`is_demo=true`)
- [ ] Cron worker logs at least one insight rule evaluation
- [ ] Mobile viewport: sidebar collapses, all pages usable on iPhone-width
- [ ] Dark mode looks intentional on every page (not just inverted)

---

## Day 7 — 17 May Paz — Demo video + README + GitHub clean-up + smoke test

### Person A — full smoke test + README technical sections

Files touched:
- `README.md` — banner, tech stack table, architecture link, demo credentials, cured by Day 7
- `docs/architecture.png` (new) — Excalidraw export, master plan §14 ASCII as visual
- `docs/demo_script.md` (new) — exact 90-sec recording flow per master plan §20

### Person B — demo video recording + README visuals

Files touched:
- `docs/demo.mp4` (new) — 90-second screen recording with Türkçe voice-over
- `docs/demo.gif` (new) — 30-sec animated GIF for the README banner
- `README.md` — visual sections (banner, GIF, screenshots)
- `LICENSE` (new) — MIT

### End-of-day checklist (Day 7)

- [ ] Live URL passes the master plan §20 demo scenarios end to end
- [ ] README renders correctly on github.com (preview the markdown)
- [ ] Demo video uploads to YouTube/repo, link in README
- [ ] `master_plan.md` references match reality (no broken anchors)
- [ ] Both have committed in the last 2 hours (judging "balanced commits" §21)

---

## Communication protocol

**Daily 21:00 sync (Discord, 30 min cap):**
1. _Done today_ — each person 5 bullets max.
2. _Tomorrow_ — each person's first 3 tasks.
3. _Blockers_ — anything that needs the other person's input or external resource.
4. _Risk check_ — anything from master plan §22 that became more or less likely.

**Branch strategy:**
- `main` is always green. No direct pushes.
- One feature branch per day per person: `pa/day-2-auth`, `pb/day-3-charts`.
- Merge as a PR before midnight; squash merge to keep `main` history clean.

**PR review rules:**
- 1 reviewer (the other person) is sufficient — we're 2 people, no committee.
- ≤24 hour SLA for review; if blocked >24h, the author may merge with self-review and comment "self-merged for velocity, please review post-merge".
- Mandatory checks: `make lint` + `make type-check` + `make test` green locally before opening the PR.
- The PR description includes:
  - Linked master plan section / İK reference
  - Sample `curl` or screenshot
  - Anything the other person needs to know

**Blocker protocol:**
- Discord ping immediately. Don't wait for the 21:00 sync.
- If the other person is heads-down: leave a written description in the GitHub issue tracker (`#blocker:` tag) so context is preserved.
- After 2h of being stuck, switch tasks and document the blocker in `docs/blockers.md`.

**Code drift guard (master plan rule):**
- If a decision conflicts with `docs/master_plan.md`, **stop coding**, update the plan in a separate `docs:` commit, then proceed. No silent deviations.
