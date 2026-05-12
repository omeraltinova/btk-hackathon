"""Transactions router: authenticated manual income/expense CRUD."""

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _visible_user_ids(current_user: User) -> list[UUID]:
    ids = [current_user.id]
    if current_user.role == "parent":
        ids.extend(child.id for child in current_user.children)
    return ids


def _get_scoped_transaction(
    transaction_id: UUID,
    current_user: User,
    db: Session,
) -> Transaction:
    transaction = db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id.in_(_visible_user_ids(current_user)),
        ),
    ).scalar_one_or_none()
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="İşlem bulunamadı.",
        )
    return transaction


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
            or_(Category.user_id == current_user.id, Category.user_id.is_(None)),
        ),
    ).scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kategori bulunamadı.",
        )


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Transaction]:
    return (
        db.execute(
            select(Transaction)
            .where(Transaction.user_id.in_(_visible_user_ids(current_user)))
            .order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc())
            .offset(offset)
            .limit(limit),
        )
        .scalars()
        .all()
    )


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Transaction:
    _ensure_category_access(payload.category_id, current_user, db)
    transaction = Transaction(
        user_id=current_user.id,
        amount=payload.amount,
        type=payload.type,
        category_id=payload.category_id,
        description=payload.description,
        merchant=payload.merchant,
        occurred_at=payload.occurred_at,
        source="manual",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("/{transaction_id}", response_model=TransactionRead)
def get_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Transaction:
    return _get_scoped_transaction(transaction_id, current_user, db)


@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: UUID,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Transaction:
    transaction = _get_scoped_transaction(transaction_id, current_user, db)
    if "category_id" in payload.model_fields_set:
        _ensure_category_access(payload.category_id, current_user, db)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)

    db.commit()
    db.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    transaction = _get_scoped_transaction(transaction_id, current_user, db)
    db.delete(transaction)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
