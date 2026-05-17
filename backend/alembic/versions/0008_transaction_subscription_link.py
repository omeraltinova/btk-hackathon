"""transactions.subscription_id link to subscriptions

Revision ID: 0008_tx_subscription_link
Revises: 0007_recurring_income
Create Date: 2026-05-17 18:00:00

Backfills the link for existing recurring rows whose `raw_ocr_data`
JSONB already stores the originating `subscription_id` so the new FK
is populated without losing history.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# WHY 25-char revision id: `alembic_version.version_num` is `varchar(32)` so the
# full descriptive form `0008_transaction_subscription_link` (34 chars) trips a
# StringDataRightTruncation on upgrade. Shortened to stay under the cap.
revision: str = "0008_tx_subscription_link"
down_revision: str | Sequence[str] | None = "0007_recurring_income"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "subscription_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        op.f("fk_transactions_subscription_id_subscriptions"),
        "transactions",
        "subscriptions",
        ["subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_transactions_subscription_id"),
        "transactions",
        ["subscription_id"],
    )
    # Backfill from raw_ocr_data so historical recurring rows already get the
    # link without a separate one-shot script.
    op.execute(
        """
        UPDATE transactions
        SET subscription_id = CAST(raw_ocr_data->>'subscription_id' AS uuid)
        WHERE source = 'recurring'
          AND raw_ocr_data ? 'subscription_id'
          AND subscription_id IS NULL
        """,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_transactions_subscription_id"), table_name="transactions")
    op.drop_constraint(
        op.f("fk_transactions_subscription_id_subscriptions"),
        "transactions",
        type_="foreignkey",
    )
    op.drop_column("transactions", "subscription_id")
