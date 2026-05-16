"""birth date family scope and custom recurrence

Revision ID: 0003_birth_recurrence
Revises: 0002_system_categories
Create Date: 2026-05-13 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_birth_recurrence"
down_revision: str | Sequence[str] | None = "0002_system_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("users", sa.Column("birth_date", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE users
        SET birth_date = make_date(
            GREATEST(EXTRACT(YEAR FROM CURRENT_DATE)::int - age, 1900),
            1,
            1
        )
        WHERE age IS NOT NULL AND birth_date IS NULL
        """,
    )
    op.execute("UPDATE users SET family_id = id WHERE role = 'parent' AND family_id IS NULL")
    op.execute(
        """
        UPDATE users child
        SET family_id = COALESCE(parent.family_id, child.parent_id)
        FROM users parent
        WHERE child.role = 'child'
          AND child.parent_id = parent.id
          AND child.family_id IS NULL
        """,
    )
    op.create_index("idx_users_family", "users", ["family_id"])
    op.drop_column("users", "age")

    op.drop_constraint(op.f("ck_subscriptions_billing_cycle_valid"), "subscriptions", type_="check")
    op.add_column(
        "subscriptions",
        sa.Column("recurrence_interval", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "subscriptions",
        sa.Column("recurrence_unit", sa.String(), server_default="month", nullable=False),
    )
    op.execute(
        """
        UPDATE subscriptions
        SET recurrence_unit = CASE billing_cycle
            WHEN 'weekly' THEN 'week'
            WHEN 'yearly' THEN 'year'
            ELSE 'month'
        END,
        recurrence_interval = 1
        """,
    )
    op.create_check_constraint(
        "billing_cycle_valid",
        "subscriptions",
        "billing_cycle IN ('weekly','monthly','yearly','custom')",
    )
    op.create_check_constraint(
        "recurrence_interval_positive",
        "subscriptions",
        "recurrence_interval >= 1",
    )
    op.create_check_constraint(
        "recurrence_unit_valid",
        "subscriptions",
        "recurrence_unit IN ('day','week','month','year')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_subscriptions_recurrence_unit_valid"),
        "subscriptions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_subscriptions_recurrence_interval_positive"),
        "subscriptions",
        type_="check",
    )
    op.drop_constraint(op.f("ck_subscriptions_billing_cycle_valid"), "subscriptions", type_="check")
    op.drop_column("subscriptions", "recurrence_unit")
    op.drop_column("subscriptions", "recurrence_interval")
    op.create_check_constraint(
        "billing_cycle_valid",
        "subscriptions",
        "billing_cycle IN ('weekly','monthly','yearly')",
    )

    op.add_column("users", sa.Column("age", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE users
        SET age = GREATEST(EXTRACT(YEAR FROM AGE(CURRENT_DATE, birth_date))::int, 0)
        WHERE birth_date IS NOT NULL
        """,
    )
    op.drop_index("idx_users_family", table_name="users")
    op.drop_column("users", "birth_date")
    op.drop_column("users", "family_id")
