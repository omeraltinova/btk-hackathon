"""Categories router: system defaults plus user-created transaction categories."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.category import Category
from app.models.saving_goal import SavingGoal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.schemas.category import CategoryBudgetUpdate, CategoryCreate, CategoryRead, EnvelopeCreate
from app.services.envelopes import (
    EnvelopeDefinition,
    category_matches_envelope,
    custom_envelope_category_id,
    envelope_definition_for_category_name,
    envelope_definition_for_slug,
)

router = APIRouter(prefix="/api/categories", tags=["categories"])


def _without_shadowed_defaults(
    categories: Sequence[Category],
    current_user: User,
) -> list[Category]:
    owned_names = {
        category.name.casefold()
        for category in categories
        if category.user_id in visible_user_ids(current_user)
    }
    visible = [
        category
        for category in categories
        if category.user_id is not None or category.name.casefold() not in owned_names
    ]
    return sorted(
        visible, key=lambda category: (category.user_id is not None, category.name.casefold())
    )


def _matching_envelope_categories(
    *,
    slug: str,
    db: Session,
    current_user: User,
) -> tuple[list[Category], EnvelopeDefinition]:
    definition = envelope_definition_for_slug(slug)
    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zarf bulunamadı.",
        )

    user_ids = visible_user_ids(current_user)
    categories = (
        db.execute(
            select(Category).where(
                or_(Category.user_id.in_(user_ids), Category.user_id.is_(None)),
            ),
        )
        .scalars()
        .all()
    )
    return [
        category for category in categories if category_matches_envelope(definition, category)
    ], definition


def _editable_envelope_category(
    *,
    slug: str,
    db: Session,
    current_user: User,
) -> Category:
    matches, definition = _matching_envelope_categories(slug=slug, db=db, current_user=current_user)
    owned = next((category for category in matches if category.user_id == current_user.id), None)
    if owned is not None:
        return owned

    system_match = next((category for category in matches if category.user_id is None), None)
    category = Category(
        user_id=current_user.id,
        name=definition.category_name,
        icon=system_match.icon if system_match is not None else None,
        parent_id=None,
        budget_monthly=None,
    )
    db.add(category)
    return category


def _get_custom_envelope_category(
    *,
    slug: str,
    db: Session,
    current_user: User,
) -> Category | None:
    category_id = custom_envelope_category_id(slug)
    if category_id is None:
        return None
    return db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == current_user.id,
        ),
    ).scalar_one_or_none()


def set_envelope_budget(
    *,
    slug: str,
    budget_monthly: Decimal,
    db: Session,
    current_user: User,
) -> Category:
    custom_category = _get_custom_envelope_category(slug=slug, db=db, current_user=current_user)
    if custom_category is not None:
        custom_category.budget_monthly = budget_monthly
        db.commit()
        db.refresh(custom_category)
        return custom_category

    category = _editable_envelope_category(slug=slug, db=db, current_user=current_user)
    category.budget_monthly = budget_monthly
    db.commit()
    db.refresh(category)
    return category


def create_envelope_category(
    *,
    name: str,
    budget_monthly: Decimal,
    db: Session,
    current_user: User,
) -> Category:
    existing = db.execute(
        select(Category).where(
            Category.user_id == current_user.id,
            func.lower(Category.name) == name.lower(),
        ),
    ).scalar_one_or_none()
    if existing is not None:
        existing.budget_monthly = budget_monthly
        db.commit()
        db.refresh(existing)
        return existing

    definition = envelope_definition_for_category_name(name)
    if definition is not None:
        return set_envelope_budget(
            slug=definition.slug,
            budget_monthly=budget_monthly,
            db=db,
            current_user=current_user,
        )

    category = Category(
        user_id=current_user.id,
        name=name,
        icon=None,
        parent_id=None,
        budget_monthly=budget_monthly,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def _clear_category_references(*, category: Category, db: Session) -> None:
    transactions = (
        db.execute(
            select(Transaction).where(Transaction.category_id == category.id),
        )
        .scalars()
        .all()
    )
    for transaction in transactions:
        transaction.category_id = None

    subscriptions = (
        db.execute(
            select(Subscription).where(Subscription.category_id == category.id),
        )
        .scalars()
        .all()
    )
    for subscription in subscriptions:
        subscription.category_id = None

    saving_goals = (
        db.execute(
            select(SavingGoal).where(SavingGoal.category_id == category.id),
        )
        .scalars()
        .all()
    )
    for goal in saving_goals:
        goal.category_id = None


def delete_envelope_category(
    *,
    slug: str,
    db: Session,
    current_user: User,
) -> Category | None:
    custom_category = _get_custom_envelope_category(slug=slug, db=db, current_user=current_user)
    custom_category_id = custom_envelope_category_id(slug)
    if custom_category is not None:
        _clear_category_references(category=custom_category, db=db)
        db.delete(custom_category)
        db.commit()
        return custom_category
    if custom_category_id is not None:
        return None

    matches, _definition = _matching_envelope_categories(
        slug=slug, db=db, current_user=current_user
    )
    owned = next((category for category in matches if category.user_id == current_user.id), None)
    if owned is None:
        return None

    _clear_category_references(category=owned, db=db)
    db.delete(owned)
    db.commit()
    return owned


@router.get("", response_model=list[CategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Sequence[Category]:
    user_ids = visible_user_ids(current_user)
    categories = (
        db.execute(
            select(Category)
            .where(or_(Category.user_id.in_(user_ids), Category.user_id.is_(None)))
            .order_by(Category.user_id.is_not(None), Category.name),
        )
        .scalars()
        .all()
    )
    return _without_shadowed_defaults(categories, current_user)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Category:
    existing = db.execute(
        select(Category).where(
            Category.user_id == current_user.id,
            func.lower(Category.name) == payload.name.lower(),
        ),
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu kategori zaten var.",
        )

    category = Category(
        user_id=current_user.id,
        name=payload.name,
        icon=payload.icon,
        parent_id=None,
        budget_monthly=payload.budget_monthly,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/envelopes/{slug}", response_model=CategoryRead)
def update_envelope_budget(
    slug: str,
    payload: CategoryBudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Category:
    return set_envelope_budget(
        slug=slug,
        budget_monthly=payload.budget_monthly,
        db=db,
        current_user=current_user,
    )


@router.post("/envelopes", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_envelope_budget(
    payload: EnvelopeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Category:
    return create_envelope_category(
        name=payload.name,
        budget_monthly=payload.budget_monthly,
        db=db,
        current_user=current_user,
    )


@router.delete("/envelopes/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_envelope_budget(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    delete_envelope_category(slug=slug, db=db, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
