"""Seed system transaction categories."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_system_categories"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

CATEGORY_IDS = (
    "8b45d2cf-3866-433c-8f53-9d9d4a3d5a10",
    "596d03cb-c6c1-41c0-8999-a7e95feb68ed",
    "7ba760e5-2926-4c24-a513-62246e8a14d6",
    "28b06785-64d5-4d7b-8b53-c1c9d199ad2f",
    "3b181340-0d8a-4f7c-97bd-625555879771",
    "04596fe4-c169-40f1-b948-ceb9a488d08f",
    "f5f4dd17-2dc0-4c1f-8803-aaeb5c8d0749",
    "e33e5b42-036d-4245-9977-a11f9224df6d",
    "d804b625-a5f4-4775-94f1-536d2eaa37f8",
    "79978d17-20fd-4747-ac75-ece5a51462af",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO categories (id, user_id, name, icon)
            VALUES
              ('8b45d2cf-3866-433c-8f53-9d9d4a3d5a10', NULL, 'Market', 'basket'),
              ('596d03cb-c6c1-41c0-8999-a7e95feb68ed', NULL, 'Fatura', 'receipt'),
              ('7ba760e5-2926-4c24-a513-62246e8a14d6', NULL, 'Ulaşım', 'bus'),
              ('28b06785-64d5-4d7b-8b53-c1c9d199ad2f', NULL, 'Kira', 'home'),
              ('3b181340-0d8a-4f7c-97bd-625555879771', NULL, 'Eğitim', 'book'),
              ('04596fe4-c169-40f1-b948-ceb9a488d08f', NULL, 'Sağlık', 'heart'),
              ('f5f4dd17-2dc0-4c1f-8803-aaeb5c8d0749', NULL, 'Eğlence', 'ticket'),
              ('e33e5b42-036d-4245-9977-a11f9224df6d', NULL, 'Giyim', 'shirt'),
              ('d804b625-a5f4-4775-94f1-536d2eaa37f8', NULL, 'Maaş', 'wallet'),
              ('79978d17-20fd-4747-ac75-ece5a51462af', NULL, 'Diğer', 'dots')
            ON CONFLICT (id) DO NOTHING
            """,
        ),
    )


def downgrade() -> None:
    ids = ", ".join(f"'{category_id}'" for category_id in CATEGORY_IDS)
    op.execute(sa.text(f"DELETE FROM categories WHERE user_id IS NULL AND id IN ({ids})"))
