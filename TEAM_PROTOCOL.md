# TEAM_PROTOCOL.md -- task-by-task assignment board

> This is the active task assignment file.
>
> The goal is to split the **total project task list** across two full-stack people. Do not split one task across two owners.

Day 1 bootstrap is already complete. This board tracks Days 2-7.

## Rules

- Every task has one owner: `Person A` or `Person B`.
- A task may include frontend, backend, database, tests, docs, or deploy work.
- If another task needs an output, that is a dependency, not shared ownership.
- Update the `Status` field during the day.
- Status values: `TODO`, `DOING`, `BLOCKED`, `DONE`.

## Summary

| Task | Day | Owner | Title | Depends on | Status |
|---|---|---|---|---|---|
| 1 | 2 | Person A | Auth flow end-to-end | None | DONE |
| 2 | 2 | Person B | Transactions feature slice + chat mock | Task 1 auth contract | DONE |
| 3 | 3 | Person A | Agent spending query + streaming backend | Task 2 transaction data | DONE |
| 4 | 3 | Person B | Dashboard analytics + streaming chat UI | Task 3 SSE contract | DONE |
| 5 | 4 | Person A | Receipt ingestion backend slice | None | DONE |
| 6 | 4 | Person B | Receipt confirmation + receipt history UI | Task 5 upload schema/API | DONE |
| 7 | 5 | Person A | Family management flow end-to-end | Task 1 auth flow | DONE |
| 8 | 5 | Person B | Child coach experience end-to-end | Task 7 family switch | DONE |
| 9 | 6 | Person A | Proactive insights + deploy | Tasks 5 and 7 data flow | DOING |
| 10 | 6 | Person B | Insight UI + mobile/dark polish | Task 9 insights API + prod URL | DOING |
| 11 | 7 | Person A | Final verification + architecture assets | Tasks 1-10 complete | TODO |
| 12 | 7 | Person B | README, demo assets, submission package | Task 11 outputs | TODO |

---

## Task 1 -- Auth flow end-to-end

- Owner: `Person A`
- Day: `2`
- Goal: Registration, login, session, and protected app access work end-to-end.
- Scope:
  - Backend auth endpoints: register, login, me
  - Auth schemas and backend auth tests
  - Frontend login/register pages
  - NextAuth credentials integration
  - Protected app layout redirect and backend token passthrough
- Main files:
  - `backend/app/routers/auth.py`
  - `backend/app/schemas/auth.py`
  - `backend/tests/test_auth.py`
  - `frontend/app/(auth)/login/page.tsx`
  - `frontend/app/(auth)/register/page.tsx`
  - `frontend/app/api/auth/[...nextauth]/route.ts`
  - `frontend/lib/auth.ts`
  - `frontend/app/(app)/layout.tsx`
- Depends on: `None`
- Done when:
  - [x] Register and login return JWT/session data
  - [x] `GET /api/auth/me` works with bearer token
  - [x] Login redirects to `/dashboard`
  - [x] Auth tests are green

## Task 2 -- Transactions feature slice + chat mock

- Owner: `Person B`
- Day: `2`
- Goal: The first post-login experience works with real transactions and a placeholder chat.
- Scope:
  - Transactions CRUD backend and schemas
  - Transaction tests
  - TS type mirror for auth/transactions
  - Dashboard transaction list UI
  - Chat page mock flow and basic `ChatStream` scaffold
- Main files:
  - `backend/app/routers/transactions.py`
  - `backend/app/schemas/transaction.py`
  - `backend/tests/test_transactions.py`
  - `frontend/app/(app)/dashboard/page.tsx`
  - `frontend/app/(app)/chat/page.tsx`
  - `frontend/components/ChatStream.tsx`
  - `frontend/lib/types.ts`
- Depends on: `Task 1 auth contract by 17:00`
- Done when:
  - [x] Authenticated `GET /api/transactions` returns user-scoped data
  - [x] Dashboard renders transaction list from real API data
  - [x] Chat mock UI is visible and usable
  - [x] Transaction tests are green

## Task 3 -- Agent spending query + streaming backend

- Owner: `Person A`
- Day: `3`
- Goal: The backend can answer spending questions through real tool calling and a real stream.
- Scope:
  - `get_spending`, `get_subscriptions`, `get_user_memory`
  - LangGraph graph and prompt wiring
  - TL/date formatting helpers
  - Chat SSE backend endpoint
  - Example SSE payload documentation
- Main files:
  - `backend/app/agent/graph.py`
  - `backend/app/agent/tools.py`
  - `backend/app/agent/prompts.py`
  - `backend/app/services/agent_runner.py`
  - `backend/app/routers/chat.py`
  - `backend/app/utils/tl_format.py`
  - `backend/app/utils/date_format.py`
  - `backend/tests/test_agent_tools.py`
  - `backend/tests/test_utils.py`
  - `docs/agent_sse_example.json`
- Depends on: `Task 2 transaction data and auth flow`
- Done when:
  - [x] Agent can answer a market-spend question from real DB data
  - [x] SSE stream works through an authenticated endpoint test; curl payload is documented
  - [x] Amount/date helpers match the project rules
  - [x] Agent/tool tests are green

## Task 4 -- Dashboard analytics + streaming chat UI

- Owner: `Person B`
- Day: `3`
- Goal: Dashboard analytics and chat UI consume the real streaming backend.
- Scope:
  - Dashboard summary cards and chart UI
  - `SpendingChart`
  - Real stream consumption in `ChatStream`
  - `ChatMessage` and tool-trace rendering
  - Typed SSE client
- Main files:
  - `frontend/app/(app)/dashboard/page.tsx`
  - `frontend/components/SpendingChart.tsx`
  - `frontend/components/InsightBanner.tsx`
  - `frontend/components/ChatStream.tsx`
  - `frontend/components/ChatMessage.tsx`
  - `frontend/lib/sse.ts`
- Depends on: `Task 3 SSE contract by 18:00`
- Done when:
  - [x] Charts render from real backend numbers
  - [x] Chat streams live backend responses
  - [x] Tool trace is visible in the UI
  - [x] UI uses `1.250,50 ₺` and `gg.aa.yyyy`

## Task 5 -- Receipt ingestion backend slice

- Owner: `Person A`
- Day: `4`
- Goal: A receipt can be uploaded and parsed into a structured candidate.
- Scope:
  - MinIO service layer
  - OCR service and structured output
  - `analyze_receipt`
  - Receipt upload API
  - Receipt schema, OCR tests, sample receipt fixtures
- Main files:
  - `backend/app/services/minio.py`
  - `backend/app/services/ocr.py`
  - `backend/app/agent/tools.py`
  - `backend/app/routers/receipts.py`
  - `backend/app/schemas/receipt.py`
  - `backend/tests/test_ocr.py`
  - `seeds/sample_receipts/migros_demo.txt`
- Depends on: `None`
- Done when:
  - [x] Upload endpoint returns parsed receipt candidate
  - [x] At least one Turkish receipt works end-to-end
  - [x] OCR tests pass
  - [x] Upload response schema is stable by 11:00

## Task 6 -- Receipt confirmation + receipt history UI

- Owner: `Person B`
- Day: `4`
- Goal: The user can review, edit, confirm, and later revisit receipt entries.
- Scope:
  - Drag-drop uploader
  - Receipt preview and edit-before-save dialog
  - Receipts page history list
  - Confirmation flow using Task 5 upload output and existing transaction create flow
- Main files:
  - `frontend/components/ReceiptUploader.tsx`
  - `frontend/components/ReceiptConfirmDialog.tsx`
  - `frontend/app/(app)/receipts/page.tsx`
- Depends on: `Task 5 upload schema/API`
- Done when:
  - [x] Drag-drop upload reaches OCR and returns preview data
  - [x] Confirming a receipt creates a transaction
  - [x] Receipt history is visible in the receipts page

## Task 7 -- Family management flow end-to-end

- Owner: `Person A`
- Day: `5`
- Goal: A parent can manage family members and switch into a child context.
- Scope:
  - Family endpoints and permission rules
  - Family-switch auth behavior
  - Demo family seeder
  - Family tests
  - Family page and family-switch UI
- Main files:
  - `backend/app/routers/family.py`
  - `backend/app/auth.py`
  - `backend/tests/test_family.py`
  - `seeds/demo_family.py`
  - `frontend/app/(app)/family/page.tsx`
  - `frontend/components/FamilySwitch.tsx`
- Depends on: `Task 1 auth flow`
- Done when:
  - [x] Parent can list family members and add a child
  - [x] Family switch returns and stores the correct child context/token
  - [x] Demo family seeder creates Ayşe, Mehmet, and Elif
  - [x] Family permission tests are green

## Task 8 -- Child coach experience end-to-end

- Owner: `Person B`
- Day: `5`
- Goal: The child-mode coaching experience feels distinct and works on real family context.
- Scope:
  - `explain_concept` and `simulate_scenario`
  - Child-mode prompt variant
  - Child-mode chat styling and badge
  - Demo run for child-language answers
- Main files:
  - `backend/app/agent/tools.py`
  - `backend/app/agent/prompts.py`
  - `frontend/app/(app)/chat/page.tsx`
  - `frontend/components/AgeAppropriateBadge.tsx`
- Depends on: `Task 7 family switch`
- Done when:
  - [x] Child-mode answers are age appropriate
  - [x] Chat UI clearly indicates child mode
  - [x] Switching to Elif and asking "Faiz nedir?" works end-to-end

## Task 9 -- Proactive insights + deploy

- Owner: `Person A`
- Day: `6`
- Goal: Proactive insights run automatically and the app is deployed.
- Scope:
  - Worker rules and scheduler startup behavior
  - Insights list/dismiss API
  - Proactive worker tests
  - Deploy config and production rollout
  - Production demo seed
- Main files:
  - `backend/app/workers/proactive.py`
  - `backend/app/main.py`
  - `backend/app/routers/insights.py`
  - `backend/tests/test_proactive_worker.py`
  - `coolify.yaml`
- Depends on: `Tasks 5 and 7 data flow`
- Done when:
  - [x] Core proactive rules work
  - [x] Insights API is stable
  - [ ] Live production URL responds with valid HTTPS
  - [ ] Demo family exists on prod with `is_demo=true`

## Task 10 -- Insight UI + mobile/dark polish

- Owner: `Person B`
- Day: `6`
- Goal: The product looks polished and exposes live proactive insights cleanly.
- Scope:
  - Live `InsightBanner` integration
  - Dashboard insight rendering
  - Mobile nav/sidebar pass
  - Mobile spacing pass
  - Dark-mode contrast pass
- Main files:
  - `frontend/app/(app)/dashboard/page.tsx`
  - `frontend/components/InsightBanner.tsx`
  - `frontend/app/globals.css`
  - `frontend/components/sidebar.tsx`
- Depends on: `Task 9 insights API + production URL`
- Done when:
  - [x] Insights render from live API data
  - [ ] iPhone-width layout is usable on all main pages
  - [ ] Dark mode looks intentional everywhere

## Task 11 -- Final verification + architecture assets

- Owner: `Person A`
- Day: `7`
- Goal: The technical side of the release is verified and documented.
- Scope:
  - Full smoke test across demo scenarios
  - Architecture diagram export
  - Demo script finalization
  - GitHub cleanup and final technical findings
- Main files:
  - `README.md` notes handed off only, no final ownership here
  - `docs/architecture.png`
  - `docs/demo_script.md`
- Depends on: `Tasks 1-10 complete`
- Done when:
  - [ ] Smoke test is complete and findings are written down
  - [ ] Architecture diagram is exported
  - [ ] Demo script is finalized
  - [ ] Cleanup notes are handed to Task 12 owner by 15:00

## Task 12 -- README, demo assets, submission package

- Owner: `Person B`
- Day: `7`
- Goal: The public package for judges is complete and ready to submit.
- Scope:
  - Full README assembly
  - Demo video recording
  - Demo GIF export
  - MIT license file
  - Form copy and submission package
- Main files:
  - `README.md`
  - `docs/demo.mp4`
  - `docs/demo.gif`
  - `LICENSE`
- Depends on: `Task 11 architecture output, demo script, and smoke-test findings`
- Done when:
  - [ ] README is complete and renders correctly on GitHub
  - [ ] Demo video and GIF are ready
  - [ ] Form copy is ready
  - [ ] Submission package is complete

---

## End-of-day note

- Current day: `Day 6 integration pass`
- Tasks in progress: `Task 9 deploy/prod seed`, `Task 10 mobile/dark polish`
- New blocker: `production deployment not started in this repo state`
- What shipped today: `LangGraph chat activation with fallback, chat receipt analysis, family switch, child coach tools, API-backed insights, scheduler-ready proactive worker`
