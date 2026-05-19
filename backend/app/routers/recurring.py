"""Recurring materialization router — explicit POST trigger.

Day 7 P1 cleanup (see `docs/decisions.md`): read endpoints used to call
`materialize_due_subscriptions` as a side effect of every GET, which broke
HTTP semantics and opened a race with concurrent dashboard loads. The
frontend now calls this endpoint explicitly on dashboard mount and after
recurring CRUD so reads stay pure.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.services.recurring_materializer import materialize_due_subscriptions

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


class MaterializeResponse(BaseModel):
    created: int


@router.post("/materialize", response_model=MaterializeResponse)
def materialize(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaterializeResponse:
    """Run the due-recurring materializer for the active scope and report new rows."""
    created = materialize_due_subscriptions(db, visible_user_ids(current_user))
    return MaterializeResponse(created=created)
