"""`proactive_insights` table — cron worker'ın ürettiği uyarılar."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProactiveInsight(TimestampMixin, Base):
    """A worker-generated insight surfaced on the dashboard banner."""

    __tablename__ = "proactive_insights"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','warning','critical')",
            name="severity_valid",
        ),
        # Partial index: only undismissed insights are queried on the dashboard.
        Index(
            "idx_insight_user",
            "user_id",
            "created_at",
            postgresql_where=text("is_dismissed = FALSE"),
        ),
    )

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
    insight_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'info'"),
    )
    action_label: Mapped[str | None] = mapped_column(String, nullable=True)
    is_dismissed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )
