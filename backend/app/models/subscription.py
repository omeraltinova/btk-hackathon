"""`subscriptions` table — algılanan veya manuel girilen abonelikler."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Subscription(TimestampMixin, Base):
    """Recurring charge bound to a user with predefined or custom intervals."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "billing_cycle IN ('weekly','monthly','yearly','custom')",
            name="billing_cycle_valid",
        ),
        CheckConstraint("recurrence_interval >= 1", name="recurrence_interval_positive"),
        CheckConstraint(
            "recurrence_unit IN ('day','week','month','year')",
            name="recurrence_unit_valid",
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
    name: Mapped[str] = mapped_column(String, nullable=False)
    merchant: Mapped[str | None] = mapped_column(String, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String, nullable=False)
    recurrence_interval: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        default=1,
    )
    recurrence_unit: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'month'"),
        default="month",
    )
    next_billing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
    )
    detected_from_transactions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )
    # WHY Numeric(3,2) (not Numeric(4,3)): scaled to 0.00–1.00 per master_plan §7.
    usage_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
