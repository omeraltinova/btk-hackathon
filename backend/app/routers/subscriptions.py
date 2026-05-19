"""Subscriptions router: authenticated recurring income and expense records."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.category import Category
from app.models.subscription import Subscription
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.schemas.subscription import SubscriptionCreate, SubscriptionRead, SubscriptionUpdate
from app.utils.recurrence import (
    monthly_equivalent,
    recurrence_from_billing_cycle,
    recurrence_label,
)

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


def _to_read(subscription: Subscription) -> SubscriptionRead:
    return SubscriptionRead(
        id=subscription.id,
        user_id=subscription.user_id,
        name=subscription.name,
        merchant=subscription.merchant,
        amount=subscription.amount,
        type=subscription.type,
        billing_cycle=subscription.billing_cycle,
        recurrence_interval=subscription.recurrence_interval,
        recurrence_unit=subscription.recurrence_unit,
        recurrence_label=recurrence_label(
            subscription.recurrence_interval,
            subscription.recurrence_unit,
            subscription.billing_cycle,
        ),
        next_billing_date=subscription.next_billing_date,
        category_id=subscription.category_id,
        is_active=subscription.is_active,
        detected_from_transactions=subscription.detected_from_transactions,
        usage_score=subscription.usage_score,
        monthly_equivalent=monthly_equivalent(
            subscription.amount,
            subscription.recurrence_interval,
            subscription.recurrence_unit,
            subscription.billing_cycle,
        ),
    )


def _validate_subscription_recurrence(subscription: Subscription) -> None:
    if subscription.billing_cycle == "custom":
        if subscription.recurrence_interval < 1 or subscription.recurrence_unit not in {
            "day",
            "week",
            "month",
            "year",
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Özel tekrar için geçerli aralık ve birim gerekli.",
            )
        return
    interval, unit = recurrence_from_billing_cycle(subscription.billing_cycle)
    subscription.recurrence_interval = interval
    subscription.recurrence_unit = unit


def _get_scoped_subscription(
    subscription_id: UUID,
    current_user: User,
    db: Session,
) -> Subscription:
    subscription = db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.user_id.in_(visible_user_ids(current_user)),
        ),
    ).scalar_one_or_none()
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tekrarlayan kayıt bulunamadı.",
        )
    return subscription


def _ensure_category_access(
    category_id: UUID | None,
    current_user: User,
    db: Session,
) -> None:
    if category_id is None:
        return
    category = db.execute(
        select(Category).where(
            Category.id == category_id,
            or_(Category.user_id.in_(visible_user_ids(current_user)), Category.user_id.is_(None)),
        ),
    ).scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kategori bulunamadı.",
        )


@router.get("", response_model=list[SubscriptionRead])
def list_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SubscriptionRead]:
    user_ids = visible_user_ids(current_user)
    subscriptions = (
        db.execute(
            select(Subscription)
            .where(Subscription.user_id.in_(user_ids))
            .order_by(
                Subscription.is_active.desc(),
                Subscription.next_billing_date.is_(None),
                Subscription.next_billing_date,
                Subscription.name,
            ),
        )
        .scalars()
        .all()
    )
    return [_to_read(subscription) for subscription in subscriptions]


@router.post("", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
def create_subscription(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionRead:
    _ensure_category_access(payload.category_id, current_user, db)
    subscription = Subscription(
        user_id=current_user.id,
        name=payload.name,
        merchant=payload.merchant,
        amount=payload.amount,
        type=payload.type,
        billing_cycle=payload.billing_cycle,
        recurrence_interval=payload.recurrence_interval or 1,
        recurrence_unit=payload.recurrence_unit or "month",
        next_billing_date=payload.next_billing_date,
        category_id=payload.category_id,
        is_active=payload.is_active,
        detected_from_transactions=False,
        usage_score=None,
    )
    _validate_subscription_recurrence(subscription)
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return _to_read(subscription)


@router.patch("/{subscription_id}", response_model=SubscriptionRead)
def update_subscription(
    subscription_id: UUID,
    payload: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubscriptionRead:
    subscription = _get_scoped_subscription(subscription_id, current_user, db)
    if "category_id" in payload.model_fields_set:
        _ensure_category_access(payload.category_id, current_user, db)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(subscription, field, value)
    _validate_subscription_recurrence(subscription)

    db.commit()
    db.refresh(subscription)
    return _to_read(subscription)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    subscription = _get_scoped_subscription(subscription_id, current_user, db)
    db.delete(subscription)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
