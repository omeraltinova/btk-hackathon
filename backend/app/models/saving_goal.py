"""Smart saving goals for expense reduction and accumulation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.user import User


class SavingGoal(TimestampMixin, Base):
    """An MVP goal to reduce spending or accumulate money for a target."""

    __tablename__ = "saving_goals"
    __table_args__ = (
        CheckConstraint("baseline_amount >= 0", name="baseline_amount_nonnegative"),
        CheckConstraint("target_spending_amount >= 0", name="target_spending_amount_nonnegative"),
        CheckConstraint("target_saving_amount >= 0", name="target_saving_amount_nonnegative"),
        CheckConstraint(
            "target_amount IS NULL OR target_amount >= 0", name="target_amount_nonnegative"
        ),
        CheckConstraint("current_amount >= 0", name="current_amount_nonnegative"),
        CheckConstraint(
            "monthly_contribution IS NULL OR monthly_contribution >= 0",
            name="monthly_contribution_nonnegative",
        ),
        CheckConstraint(
            "goal_type IN ('expense_reduction','accumulation')",
            name="goal_type_valid",
        ),
        CheckConstraint("end_date > start_date", name="date_range_valid"),
        CheckConstraint("status IN ('active','completed','paused')", name="status_valid"),
        CheckConstraint("created_by IN ('manual','agent')", name="created_by_valid"),
        Index("idx_saving_goals_user_status", "user_id", "status"),
        Index("idx_saving_goals_user_type_status", "user_id", "goal_type", "status"),
        Index("idx_saving_goals_category", "category_id"),
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
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    goal_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'expense_reduction'"),
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    baseline_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    target_spending_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    target_saving_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    target_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    current_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default=text("0"),
    )
    monthly_contribution: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'active'"))
    strategy: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'manual'"))

    user: Mapped[User] = relationship("User")
    category: Mapped[Category | None] = relationship("Category")
