"""Categories router: system defaults plus user-created transaction categories."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.category import Category
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.schemas.category import CategoryCreate, CategoryRead

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
