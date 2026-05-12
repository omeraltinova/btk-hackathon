from __future__ import annotations

from uuid import UUID

from app.models.user import User


def visible_user_ids(current_user: User) -> list[UUID]:
    ids = [current_user.id]
    if current_user.role == "parent":
        ids.extend(child.id for child in current_user.children)
    return ids
