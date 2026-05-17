"""`transactions` table — gelir ve giderler. İK-1, İK-2, İK-3 burada zorlanır."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Transaction(TimestampMixin, Base):
    """A money movement — manual entry, OCR-derived, or recurring."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('income','expense')",
            name="type_valid",
        ),
        CheckConstraint(
            "source IN ('manual','receipt_ocr','recurring')",
            name="source_valid",
        ),
        # WHY: master_plan §15 specifies these 3 indexes for hot read paths
        # (recent transactions per user, by category, by merchant).
        Index("idx_tx_user_date", "user_id", text("occurred_at DESC")),
        Index("idx_tx_category", "category_id"),
        Index("idx_tx_merchant", "merchant"),
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
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=True,
    )
    subscription_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    merchant: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'manual'"),
    )
    receipt_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_ocr_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="transactions")
