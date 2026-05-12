"""Family router: parent-managed child profiles and context switch tokens."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user
from app.config import get_settings
from app.db import get_db
from app.models.user import User
from app.schemas.auth import AuthUser, TokenResponse
from app.schemas.family import ChildCreate, ChildUpdate, FamilyMemberRead

router = APIRouter(prefix="/api/family", tags=["family"])


def _ensure_parent(current_user: User) -> None:
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aile yönetimi için ebeveyn hesabı gerekli.",
        )


def _get_child(child_id: UUID, current_user: User, db: Session) -> User:
    child = db.execute(
        select(User).where(
            User.id == child_id,
            User.parent_id == current_user.id,
            User.role == "child",
        ),
    ).scalar_one_or_none()
    if child is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Çocuk profili bulunamadı.",
        )
    return child


def _child_email(parent: User) -> str:
    return f"child-{uuid4()}@{parent.id}.cuzdan-kocu.local"


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_token(user.id),
        expires_in_days=get_settings().jwt_expire_days,
        user=AuthUser.model_validate(user),
    )


@router.get("", response_model=list[FamilyMemberRead])
def list_family_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    if current_user.role == "child":
        return [current_user]
    _ensure_parent(current_user)
    children = (
        db.execute(
            select(User)
            .where(User.parent_id == current_user.id, User.role == "child")
            .order_by(User.created_at, User.name),
        )
        .scalars()
        .all()
    )
    return [current_user, *children]


@router.post("/children", response_model=FamilyMemberRead, status_code=status.HTTP_201_CREATED)
def create_child(
    payload: ChildCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    _ensure_parent(current_user)
    child = User(
        email=_child_email(current_user),
        name=payload.name,
        role="child",
        parent_id=current_user.id,
        password_hash=None,
        age=payload.age,
        finance_level=payload.finance_level,
        is_demo=current_user.is_demo,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


@router.patch("/children/{child_id}", response_model=FamilyMemberRead)
def update_child(
    child_id: UUID,
    payload: ChildUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    _ensure_parent(current_user)
    child = _get_child(child_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(child, field, value)
    db.commit()
    db.refresh(child)
    return child


@router.post("/switch/{child_id}", response_model=TokenResponse)
def switch_to_child(
    child_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    _ensure_parent(current_user)
    child = _get_child(child_id, current_user, db)
    return _token_response(child)
