from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.models.user import User


def visible_user_ids(current_user: User) -> list[UUID]:
    ids = [current_user.id]
    if current_user.role == "parent":
        session = object_session(current_user)
        if current_user.family_id is not None and session is not None:
            family_ids = session.execute(
                select(User.id).where(
                    User.family_id == current_user.family_id,
                    User.role.in_(("parent", "child")),
                ),
            ).scalars()
            return list(dict.fromkeys([current_user.id, *family_ids]))
        ids.extend(child.id for child in current_user.children)
    return list(dict.fromkeys(ids))
