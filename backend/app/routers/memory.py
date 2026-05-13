"""Agent memory viewer.

Strict per-user scope (İK-4 in its strictest form): each user can list and
delete only their own `agent_memory` rows. Parents cannot view children's
memory without family-switching into the child profile first.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.memory import AgentMemory
from app.models.user import User
from app.schemas.memory import MemoryEntry

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=list[MemoryEntry])
def list_memory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MemoryEntry]:
    rows = list(
        db.execute(
            select(AgentMemory)
            .where(AgentMemory.user_id == current_user.id)
            .order_by(AgentMemory.updated_at.desc(), AgentMemory.key),
        )
        .scalars()
        .all(),
    )
    return [
        MemoryEntry(
            key=row.key,
            value=row.value,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    row = db.execute(
        select(AgentMemory).where(
            AgentMemory.user_id == current_user.id,
            AgentMemory.key == key,
        ),
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu hafıza kaydı bulunamadı.",
        )
    db.delete(row)
    db.commit()
