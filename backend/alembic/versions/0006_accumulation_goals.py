"""accumulation goals

Revision ID: 0006_accumulation_goals
Revises: 0005_saving_goals
Create Date: 2026-05-14 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_accumulation_goals"
down_revision: str | Sequence[str] | None = "0005_saving_goals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "saving_goals",
        sa.Column(
            "goal_type",
            sa.String(),
            server_default=sa.text("'expense_reduction'"),
            nullable=False,
        ),
    )
    op.add_column("saving_goals", sa.Column("target_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "saving_goals",
        sa.Column("current_amount", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "saving_goals",
        sa.Column("monthly_contribution", sa.Numeric(12, 2), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_saving_goals_goal_type_valid"),
        "saving_goals",
        "goal_type IN ('expense_reduction','accumulation')",
    )
    op.create_check_constraint(
        op.f("ck_saving_goals_target_amount_nonnegative"),
        "saving_goals",
        "target_amount IS NULL OR target_amount >= 0",
    )
    op.create_check_constraint(
        op.f("ck_saving_goals_current_amount_nonnegative"),
        "saving_goals",
        "current_amount >= 0",
    )
    op.create_check_constraint(
        op.f("ck_saving_goals_monthly_contribution_nonnegative"),
        "saving_goals",
        "monthly_contribution IS NULL OR monthly_contribution >= 0",
    )
    op.create_index(
        "idx_saving_goals_user_type_status",
        "saving_goals",
        ["user_id", "goal_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_saving_goals_user_type_status", table_name="saving_goals")
    op.drop_constraint(
        op.f("ck_saving_goals_monthly_contribution_nonnegative"),
        "saving_goals",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_saving_goals_current_amount_nonnegative"),
        "saving_goals",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_saving_goals_target_amount_nonnegative"),
        "saving_goals",
        type_="check",
    )
    op.drop_constraint(op.f("ck_saving_goals_goal_type_valid"), "saving_goals", type_="check")
    op.drop_column("saving_goals", "monthly_contribution")
    op.drop_column("saving_goals", "current_amount")
    op.drop_column("saving_goals", "target_amount")
    op.drop_column("saving_goals", "goal_type")
