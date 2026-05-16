"""Proactive insights router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.insight import ProactiveInsight
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.schemas.insight import InsightRead
from app.services.insights import list_active_insights, refresh_insights_for_user

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("", response_model=list[InsightRead])
def list_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProactiveInsight]:
    return list_active_insights(db, current_user)


@router.post("/refresh", response_model=list[InsightRead])
def refresh_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProactiveInsight]:
    return refresh_insights_for_user(db, current_user)


@router.patch("/{insight_id}/dismiss", response_model=InsightRead)
def dismiss_insight(
    insight_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProactiveInsight:
    insight = db.execute(
        select(ProactiveInsight).where(
            ProactiveInsight.id == insight_id,
            ProactiveInsight.user_id.in_(visible_user_ids(current_user)),
        ),
    ).scalar_one_or_none()
    if insight is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="İçgörü bulunamadı.",
        )
    insight.is_dismissed = True
    db.commit()
    db.refresh(insight)
    return insight
