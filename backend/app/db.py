"""SQLAlchemy 2.0 engine + session factory.

WHY a sync engine (not async): the agent layer (LangGraph) and Alembic both
work most simply with a sync session; FastAPI is happy to run sync DB calls in
a worker thread. We can switch to async later without touching call sites if
we wrap everything behind the `get_db` dependency.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _build_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
        # SQL echo includes bound parameters such as password hashes and receipt
        # metadata. Keep it off even when APP_DEBUG=true.
        echo=False,
    )


engine: Engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a session scoped to one request, rollback on error."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
