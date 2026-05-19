"""recurring income support

Revision ID: 0007_recurring_income
Revises: 0006_accumulation_goals
Create Date: 2026-05-17 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_recurring_income"
down_revision: str | Sequence[str] | None = "0006_accumulation_goals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("type", sa.String(), server_default=sa.text("'expense'"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_subscriptions_type_valid"),
        "subscriptions",
        "type IN ('income','expense')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_subscriptions_type_valid"), "subscriptions", type_="check")
    op.drop_column("subscriptions", "type")
