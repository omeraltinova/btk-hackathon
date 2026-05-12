"""Scheduler-ready proactive insight worker.

Run manually with:
    uv run python -m app.workers.proactive

Production schedulers can call POST /api/insights/refresh per user session, or
adapt `refresh_all_insights` for a privileged platform job.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.user import User
from app.services.insights import refresh_insights_for_user


def refresh_all_insights(db: Session) -> int:
    users = list(db.execute(select(User).where(User.role != "child")).scalars().all())
    for user in users:
        refresh_insights_for_user(db, user)
    return len(users)


def main() -> None:
    with SessionLocal() as db:
        refresh_all_insights(db)


if __name__ == "__main__":
    main()
