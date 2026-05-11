"""`agent_memory` table — kalıcı kullanıcı bilgisi (key/value, JSONB).

İK-9: upsert ile yazılır (`ON CONFLICT (user_id, key) DO UPDATE`).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AgentMemory(TimestampMixin, Base):
    """Per-user agent memory entry — one row per (user_id, key) pair."""

    __tablename__ = "agent_memory"
    __table_args__ = (UniqueConstraint("user_id", "key", name="agent_memory_user_id_key_key"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
