"""Add income and expense system categories.

Revision ID: 0004_income_categories
Revises: 0003_birth_recurrence
Create Date: 2026-05-13 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_income_categories"
down_revision: str | Sequence[str] | None = "0003_birth_recurrence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORY_IDS = (
    "1e706a8f-6f20-4cc1-96b8-0b38f0634e01",
    "ad52d06f-7a7f-4602-9640-4618412a1b17",
    "d824d86c-6745-48ea-993a-dbdfeabfb7e6",
    "3f6ec219-e58c-43ea-ae5a-0e362d5e0fd2",
    "85bc6c2e-bd6d-49e7-b996-16068007398e",
    "90c4db0b-a3d6-4240-b766-68c05e6ab83b",
    "7b27eefc-4866-427f-8fb9-20b56e74f4fb",
    "6ee97683-c05a-4c50-8f0e-b590d61904e6",
    "a388e478-7f97-4ced-b899-ab204dc67786",
    "00bbd0c5-5531-4421-b934-eec99c6e9168",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO categories (id, user_id, name, icon)
            VALUES
              ('1e706a8f-6f20-4cc1-96b8-0b38f0634e01', NULL, 'Harçlık', 'piggy-bank'),
              ('ad52d06f-7a7f-4602-9640-4618412a1b17', NULL, 'Staj', 'briefcase'),
              ('d824d86c-6745-48ea-993a-dbdfeabfb7e6', NULL, 'Hediye', 'gift'),
              ('3f6ec219-e58c-43ea-ae5a-0e362d5e0fd2', NULL, 'Freelance', 'laptop'),
              ('85bc6c2e-bd6d-49e7-b996-16068007398e', NULL, 'Faiz geliri', 'percent'),
              ('90c4db0b-a3d6-4240-b766-68c05e6ab83b', NULL, 'Diğer gelir', 'plus'),
              ('7b27eefc-4866-427f-8fb9-20b56e74f4fb', NULL, 'Yemek', 'utensils'),
              ('6ee97683-c05a-4c50-8f0e-b590d61904e6', NULL, 'Akaryakıt', 'fuel'),
              ('a388e478-7f97-4ced-b899-ab204dc67786', NULL, 'Telekom', 'phone'),
              ('00bbd0c5-5531-4421-b934-eec99c6e9168', NULL, 'Ev', 'sofa')
            ON CONFLICT (id) DO NOTHING
            """,
        ),
    )


def downgrade() -> None:
    ids = ", ".join(f"'{category_id}'" for category_id in CATEGORY_IDS)
    op.execute(sa.text(f"DELETE FROM categories WHERE user_id IS NULL AND id IN ({ids})"))
