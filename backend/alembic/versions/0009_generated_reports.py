"""generated monthly reports

Revision ID: 0009_generated_reports
Revises: 0008_tx_subscription_link
Create Date: 2026-05-18 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_generated_reports"
down_revision: str | Sequence[str] | None = "0008_tx_subscription_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generated_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.String(), nullable=False),
        sa.Column("included_user_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("object_name", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("file_size_bytes >= 0", name=op.f("ck_generated_reports_file_size_nonnegative")),
        sa.CheckConstraint("format IN ('docx','pdf')", name=op.f("ck_generated_reports_format_valid")),
        sa.CheckConstraint("scope_type IN ('self','family')", name=op.f("ck_generated_reports_scope_type_valid")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_generated_reports_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generated_reports")),
    )
    op.create_index(
        "idx_generated_reports_user_date",
        "generated_reports",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_generated_reports_user_date", table_name="generated_reports")
    op.drop_table("generated_reports")
