"""Test fixtures.

WHY override the DB URL here: tests must never hit the dev or prod database.
We point at a non-existent local Postgres URL by default; tests that don't
touch the DB (like the /health smoke test) won't actually open a connection
because lazy-init in db.py only connects on first query.
"""

from __future__ import annotations

import os

# Set env BEFORE app imports happen.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_DEBUG", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost:5432/cuzdan_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret")
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "gemini"
