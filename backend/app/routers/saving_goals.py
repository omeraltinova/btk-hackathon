"""Category-based expense reduction goal endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.saving_goal import SavingGoal
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.schemas.saving_goal import (
    SavingGoalCreate,
    SavingGoalProgressRead,
    SavingGoalRead,
    SavingGoalUpdate,
)
from app.services.saving_goals import (
    calculate_saving_goal_progress,
    create_accumulation_goal,
    create_saving_goal,
    serialize_saving_goal,
    update_saving_goal,
)

router = APIRouter(prefix="/api/saving-goals", tags=["saving-goals"])


def _get_scoped_goal(goal_id: UUID, current_user: User, db: Session) -> SavingGoal:
    goal = db.execute(
        select(SavingGoal).where(
            SavingGoal.id == goal_id,
            SavingGoal.user_id.in_(visible_user_ids(current_user)),
        ),
    ).scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hedef bulunamadı.")
    return goal


@router.get("", response_model=list[SavingGoalRead])
def list_saving_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[SavingGoalRead]:
    query = select(SavingGoal).where(SavingGoal.user_id.in_(visible_user_ids(current_user)))
    if status_filter is not None:
        query = query.where(SavingGoal.status == status_filter)
    goals = db.execute(query.order_by(SavingGoal.created_at.desc())).scalars().all()
    return [serialize_saving_goal(db, goal) for goal in goals]


@router.post("", response_model=SavingGoalRead, status_code=status.HTTP_201_CREATED)
def create_saving_goal_endpoint(
    payload: SavingGoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavingGoalRead:
    try:
        if payload.goal_type == "accumulation":
            if payload.target_amount is None or payload.target_date is None:
                raise ValueError("Birikim hedefi için hedef tutar ve tarih gerekli.")
            goal = create_accumulation_goal(
                db,
                current_user,
                target_amount=payload.target_amount,
                current_amount=payload.current_amount,
                monthly_contribution=payload.monthly_contribution,
                target_date=payload.target_date,
                title=payload.title,
                created_by="manual",
            )
        else:
            goal = create_saving_goal(
                db,
                current_user,
                category_id=payload.category_id,
                category_name=payload.category_name,
                target_reduction_percent=payload.target_reduction_percent,
                baseline_amount=payload.baseline_amount,
                title=payload.title,
                created_by="manual",
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return serialize_saving_goal(db, goal)


@router.get("/{goal_id}/progress", response_model=SavingGoalProgressRead)
def get_saving_goal_progress(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavingGoalProgressRead:
    goal = _get_scoped_goal(goal_id, current_user, db)
    return calculate_saving_goal_progress(db, goal)


@router.patch("/{goal_id}", response_model=SavingGoalRead)
def update_saving_goal_endpoint(
    goal_id: UUID,
    payload: SavingGoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavingGoalRead:
    goal = _get_scoped_goal(goal_id, current_user, db)
    try:
        updated = update_saving_goal(db, goal, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return serialize_saving_goal(db, updated)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saving_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    goal = _get_scoped_goal(goal_id, current_user, db)
    db.delete(goal)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
