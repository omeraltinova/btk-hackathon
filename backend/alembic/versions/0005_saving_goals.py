"""category expense reduction goals

Revision ID: 0005_saving_goals
Revises: 0004_income_categories
Create Date: 2026-05-13 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_saving_goals"
down_revision: str | Sequence[str] | None = "0004_income_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saving_goals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("baseline_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("target_spending_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("target_saving_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("strategy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.String(), server_default=sa.text("'manual'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("baseline_amount >= 0", name=op.f("ck_saving_goals_baseline_amount_nonnegative")),
        sa.CheckConstraint("target_spending_amount >= 0", name=op.f("ck_saving_goals_target_spending_amount_nonnegative")),
        sa.CheckConstraint("target_saving_amount >= 0", name=op.f("ck_saving_goals_target_saving_amount_nonnegative")),
        sa.CheckConstraint("end_date > start_date", name=op.f("ck_saving_goals_date_range_valid")),
        sa.CheckConstraint("status IN ('active','completed','paused')", name=op.f("ck_saving_goals_status_valid")),
        sa.CheckConstraint("created_by IN ('manual','agent')", name=op.f("ck_saving_goals_created_by_valid")),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_saving_goals_user_status", "saving_goals", ["user_id", "status"])
    op.create_index("idx_saving_goals_category", "saving_goals", ["category_id"])


def downgrade() -> None:
    op.drop_index("idx_saving_goals_category", table_name="saving_goals")
    op.drop_index("idx_saving_goals_user_status", table_name="saving_goals")
    op.drop_table("saving_goals")
