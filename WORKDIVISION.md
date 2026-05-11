# WORKDIVISION.md -- collaboration rules for single-owner tasks

> `TEAM_PROTOCOL.md` is the active task list.
>
> This file only defines how two people collaborate once tasks are assigned.

## Core rule

- Each task has exactly one owner.
- A task can contain frontend, backend, DB, tests, docs, and deploy work together.
- If a file belongs to Task `N`, only the owner of Task `N` edits it unless ownership is explicitly reassigned.
- If ownership changes, update `TEAM_PROTOCOL.md` first.

## Dependency rule

- A dependency is not shared ownership.
- The producer finishes and publishes the output.
- The consumer starts integration after the producer output is merged or handed off.
- If a dependency slips by more than 2 hours, mark the dependent task `BLOCKED` in `TEAM_PROTOCOL.md`.

## Branch strategy

- `main` stays green.
- Use one branch per task:
  - `person-a/task-1-auth-flow`
  - `person-b/task-2-transactions`
- Merge as a PR before midnight when possible.

## PR rule

- One PR should map to one task whenever practical.
- The PR description should include:
  - task number
  - relevant master plan section or invariant
  - sample curl, screenshot, or short verification note
  - anything the dependent task owner needs next

## Review rule

- The other person reviews the PR.
- Local checks before review: `make lint`, `make type-check`, `make test`.
- If blocked for more than 24 hours, self-merge is allowed with a written note.

## Blocker rule

- Ping immediately on Discord.
- Do not wait for the nightly sync.
- After 2 hours blocked, switch to another unblocked task only if it does not create ownership overlap.
- Record the blocker in `TEAM_PROTOCOL.md`.

## Nightly sync

Every day at 21:00:

1. Person A reports task status in 5 bullets max.
2. Person B reports task status in 5 bullets max.
3. Blockers and slipped dependencies are recorded.
4. `TEAM_PROTOCOL.md` is updated before the call ends.

## Code drift guard

- If a task requires a decision that contradicts `docs/master_plan.md`, stop.
- Update the plan first.
- Then continue implementation.
