"""Transactions router: authenticated manual income/expense CRUD."""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.schemas.transaction import (
    TransactionCategoryTotal,
    TransactionCreate,
    TransactionRead,
    TransactionSummaryRead,
    TransactionUpdate,
)
from app.services.recurring_materializer import materialize_due_subscriptions

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

ISTANBUL = ZoneInfo("Europe/Istanbul")
MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.1")


def _get_scoped_transaction(
    transaction_id: UUID,
    current_user: User,
    db: Session,
) -> Transaction:
    transaction = db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id.in_(visible_user_ids(current_user)),
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
            or_(Category.user_id.in_(visible_user_ids(current_user)), Category.user_id.is_(None)),
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
    user_ids = visible_user_ids(current_user)
    materialize_due_subscriptions(db, user_ids)
    return (
        db.execute(
            select(Transaction)
            .where(Transaction.user_id.in_(user_ids))
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
        source=payload.source,
        receipt_image_url=payload.receipt_image_url,
        raw_ocr_data=payload.raw_ocr_data,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _previous_month_start(value: datetime) -> datetime:
    if value.month == 1:
        return value.replace(year=value.year - 1, month=12)
    return value.replace(month=value.month - 1)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _change_percent(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return (((current - previous) / previous) * Decimal("100")).quantize(
        PERCENT_QUANT,
        rounding=ROUND_HALF_UP,
    )


@router.get("/summary", response_model=TransactionSummaryRead)
def get_transaction_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionSummaryRead:
    now = datetime.now(ISTANBUL)
    current_start = _month_start(now)
    previous_start = _previous_month_start(current_start)
    user_ids = visible_user_ids(current_user)
    materialize_due_subscriptions(db, user_ids, today=now.date())

    categories = (
        db.execute(
            select(Category).where(or_(Category.user_id.in_(user_ids), Category.user_id.is_(None))),
        )
        .scalars()
        .all()
    )
    category_names = {category.id: category.name for category in categories}

    transactions = (
        db.execute(
            select(Transaction).where(
                Transaction.user_id.in_(user_ids),
                Transaction.occurred_at >= previous_start.astimezone(UTC),
            ),
        )
        .scalars()
        .all()
    )

    income = Decimal("0")
    expense = Decimal("0")
    previous_income = Decimal("0")
    previous_expense = Decimal("0")
    category_totals: dict[UUID | None, Decimal] = {}

    for transaction in transactions:
        occurred_at = _as_aware_utc(transaction.occurred_at).astimezone(ISTANBUL)
        amount = Decimal(transaction.amount)
        if occurred_at >= current_start:
            if transaction.type == "income":
                income += amount
            else:
                expense += amount
                category_totals[transaction.category_id] = (
                    category_totals.get(transaction.category_id, Decimal("0")) + amount
                )
        elif occurred_at >= previous_start:
            if transaction.type == "income":
                previous_income += amount
            else:
                previous_expense += amount

    category_total_sum = sum(category_totals.values(), Decimal("0"))
    category_rows = [
        TransactionCategoryTotal(
            category_id=category_id,
            category_name=category_names.get(category_id, "Kategorisiz")
            if category_id is not None
            else "Kategorisiz",
            amount=_money(amount),
            percentage=(
                Decimal("0")
                if category_total_sum == 0
                else ((amount / category_total_sum) * Decimal("100")).quantize(
                    PERCENT_QUANT,
                    rounding=ROUND_HALF_UP,
                )
            ),
        )
        for category_id, amount in sorted(
            category_totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    return TransactionSummaryRead(
        period_start=current_start,
        period_end=now,
        income=_money(income),
        expense=_money(expense),
        balance=_money(income - expense),
        previous_income=_money(previous_income),
        previous_expense=_money(previous_expense),
        income_change_percent=_change_percent(income, previous_income),
        expense_change_percent=_change_percent(expense, previous_expense),
        category_totals=category_rows,
    )


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
