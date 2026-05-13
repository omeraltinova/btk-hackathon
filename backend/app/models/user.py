"""`users` table — kullanıcı ve aile graph'ı (parent_id self-FK)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.utils.age import age_status, calculate_age

if TYPE_CHECKING:
    # Avoid circular imports at runtime; only used for type hints.
    from app.models.transaction import Transaction


class User(TimestampMixin, Base):
    """Application user. role ∈ {parent, child, individual} (master_plan §15).

    Invariants encoded here:
    - email UNIQUE NOT NULL.
    - role CHECK constraint matches the SQL in master_plan §15.
    - parent_id is a self-FK with ON DELETE CASCADE: deleting a parent removes
      their children too (İK-1, İK-5).
    - password_hash is NULLABLE: child accounts log in via parent's family
      switch and have no password (decided 11 May 2026, see master_plan §15 v0.3 note).
      The application layer (auth router on Day 2) will reject login attempts
      for users whose password_hash is NULL.
    """

    __tablename__ = "users"
    __table_args__ = (
        # Constraint names: naming convention prepends `ck_<table>_`, so use a
        # short suffix here to avoid `ck_users_users_role_check`-style duplication.
        CheckConstraint(
            "role IN ('parent','child','individual')",
            name="role_valid",
        ),
        CheckConstraint(
            "finance_level IN ('beginner','intermediate','advanced','child')",
            name="finance_level_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    family_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    finance_level: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'beginner'"),
    )
    is_demo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )

    # ----- Relationships -----
    parent: Mapped[User | None] = relationship(
        "User",
        remote_side="User.id",
        back_populates="children",
    )
    children: Mapped[list[User]] = relationship(
        "User",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def age(self) -> int | None:
        return calculate_age(self.birth_date)

    @property
    def age_status(self) -> str | None:
        return age_status(self.birth_date)
