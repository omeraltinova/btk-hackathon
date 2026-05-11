# AGENTS.md — Operating rules for coding agents in this repo

This project is **Cüzdan Koçu**, a proactive AI finance coach for Turkish families, built for the BTK Hackathon.

**Two documents you must read before changing anything:**

1. **[`docs/master_plan.md`](docs/master_plan.md)** — the **constitution**. Vision, schema, scope, day-by-day plan. High-stability. If a decision contradicts the plan, **stop and update the plan first** (bump its version), then code. Do not let code drift from the plan silently.
2. **[`docs/decisions.md`](docs/decisions.md)** — the **engineering journal**. Tool quirks, non-obvious trade-offs, library workarounds, open questions, deferred decisions. Append-only chronological log. **Read the latest entries** so you don't repeat mistakes or re-discover the same gotchas.

**When you finish a chunk of work, append to `docs/decisions.md`** with anything the next agent should know that doesn't belong in the constitution. The file's header explains the format. If the learning is architectural (schema, scope, day-plan change), update `master_plan.md` **too**, bump its version, and reference the bump in your `decisions.md` entry.

**To run the project for testing**, follow [`SETUP.md`](SETUP.md). The `make` targets in the top-level `Makefile` are the canonical commands.

## The 10 operating rules (from `docs/master_plan.md` §27)

1. Before starting any new feature, re-read the relevant user story (US-1..US-10) and invariants (İK-1..İK-15) in `docs/master_plan.md`.
2. Every endpoint that reads or writes data **must filter by `user_id`** (İK-4, İK-5). A child only sees its own rows; a parent sees their own + all rows for users with `parent_id = self.id`.
3. Money is `NUMERIC(12,2)` in the DB and `Decimal` in Python — **never `float`** (İK-2). Timestamps are `TIMESTAMPTZ` and stored in UTC, formatted in the local Europe/Istanbul timezone for the user (İK-3).
4. All user-facing text (UI strings, errors, toasts, agent replies) is in **Turkish**. Money is rendered as `1.250,50 ₺` (period thousands, comma decimal, ₺ after, space). Dates are rendered as `gg.aa.yyyy`.
5. In LangGraph tool calls, **`user_id` comes from agent state, never from the user's prompt** (İK-7) — this is a prompt-injection defense.
6. If a feature is out of scope, add it to §12.3 stretch in `docs/master_plan.md`. Do not silently extend scope.
7. If a design principle (§5 P1–P10) would be violated by a proposed change, update `docs/master_plan.md` first with the rationale, then code.
8. Passwords are hashed with bcrypt or argon2id (§10). API keys, raw OCR output, receipt base64, IBANs, card numbers and ID numbers must **never** be logged (İK-15).
9. Demo data is flagged `is_demo=true` (İK-13) so it never mixes with real user data.
10. Before the final commit of a feature, sanity-check: every UI string Turkish? every amount with `₺`? every date `gg.aa.yyyy`? every router applies the `user_id` filter?

## Coding rule 11 (added in master plan v0.3)

Every table has both `created_at` and `updated_at` columns:

```python
created_at: Mapped[datetime] = mapped_column(server_default=func.now())
updated_at: Mapped[datetime] = mapped_column(
    server_default=func.now(), onupdate=func.now()
)
```

## Quality bar (non-negotiable)

- **Backend:** Python 3.12, `uv` for dependency management, `ruff` for lint+format, `mypy --strict` clean.
- **Frontend:** Next.js 15 App Router, TypeScript `strict: true`, `pnpm` for dependency management, `eslint` clean, no `any` without an inline justification.
- **Code comments and commit messages in English.** All user-visible strings (UI, errors, agent output) in **Turkish**.
- Every router today (Day 1) is a stub — **no business logic** until the relevant day's task in `docs/master_plan.md` §18 begins.
