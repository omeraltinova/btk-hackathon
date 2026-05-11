"""Typed application settings, sourced from environment / `.env`.

WHY pydantic-settings: gives us a single, typed Settings object cached as a
singleton via lru_cache; routes/services depend on `get_settings()` so tests
can override via dependency-overrides without monkey-patching globals.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Read once from env at process start."""

    model_config = SettingsConfigDict(
        # WHY: `.env` lives at repo root, not inside backend/. extra="ignore" lets
        # backend tolerate frontend-only vars (NEXT_PUBLIC_*) in the same .env.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_env: Literal["development", "production", "test"] = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_cors_origins: str = "http://localhost:3000"

    # ---- Database ----
    database_url: str = "postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan"

    # ---- Auth / JWT (İK-12: 7 days, no refresh) ----
    jwt_secret: str = Field(
        default="change-me-please-use-openssl-rand-hex-32",
        min_length=16,
        description="HS256 signing secret. Override in .env for any non-toy use.",
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    # ---- LLM / Gemini (Day 2+) ----
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    # ---- MinIO (Day 4+) ----
    minio_endpoint: str = "minio:9000"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket_receipts: str = "receipts"
    minio_region: str = "us-east-1"
    minio_use_ssl: bool = False

    @field_validator("app_cors_origins")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return ",".join(o.strip() for o in v.split(",") if o.strip())

    @property
    def cors_origins_list(self) -> list[str]:
        return [o for o in self.app_cors_origins.split(",") if o]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()
