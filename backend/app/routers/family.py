"""Family router: parent-managed child profiles and context switch tokens."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user
from app.config import get_settings
from app.db import get_db
from app.models.category import Category
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.auth import AuthUser, TokenResponse
from app.schemas.family import (
    ChildCreate,
    ChildUpdate,
    FamilyMemberCategoryBreakdown,
    FamilyMemberFinanceRead,
    FamilyMemberRead,
    FamilyOverviewRead,
)
from app.utils.recurrence import monthly_equivalent

router = APIRouter(prefix="/api/family", tags=["family"])
ISTANBUL = ZoneInfo("Europe/Istanbul")
MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.01")


def _ensure_parent(current_user: User) -> None:
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aile yönetimi için ebeveyn hesabı gerekli.",
        )


def _get_child(child_id: UUID, current_user: User, db: Session) -> User:
    criteria = [
        User.id == child_id,
        User.role == "child",
    ]
    if current_user.family_id is not None:
        criteria.append(User.family_id == current_user.family_id)
    else:
        criteria.append(User.parent_id == current_user.id)
    child = db.execute(
        select(User).where(*criteria),
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


def _list_children(current_user: User, db: Session) -> list[User]:
    return list(
        db.execute(
            select(User)
            .where(User.parent_id == current_user.id, User.role == "child")
            .order_by(User.created_at, User.name),
        )
        .scalars()
        .all()
    )


def _ensure_family_id(current_user: User) -> UUID:
    if current_user.family_id is None:
        current_user.family_id = current_user.id
    return current_user.family_id


def _list_family_members(current_user: User, db: Session) -> list[User]:
    if current_user.family_id is None:
        return [current_user, *_list_children(current_user, db)]
    return list(
        db.execute(
            select(User)
            .where(
                User.family_id == current_user.family_id,
                User.role.in_(("parent", "child")),
            )
            .order_by(User.role.desc(), User.created_at, User.name),
        )
        .scalars()
        .all()
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _percent(part: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0.00")
    return ((part / total) * Decimal("100")).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@router.get("", response_model=list[FamilyMemberRead])
def list_family_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    if current_user.role == "child":
        return [current_user]
    _ensure_parent(current_user)
    return _list_family_members(current_user, db)


@router.get("/overview", response_model=FamilyOverviewRead)
def family_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FamilyOverviewRead:
    _ensure_parent(current_user)
    members = _list_family_members(current_user, db)
    user_ids = [member.id for member in members]
    now = datetime.now(ISTANBUL)
    period_start = _month_start(now)

    transactions = (
        db.execute(
            select(Transaction).where(
                Transaction.user_id.in_(user_ids),
                Transaction.occurred_at >= period_start.astimezone(UTC),
            ),
        )
        .scalars()
        .all()
    )
    subscriptions = (
        db.execute(
            select(Subscription).where(
                Subscription.user_id.in_(user_ids),
                Subscription.is_active.is_(True),
            ),
        )
        .scalars()
        .all()
    )

    income_by_user = dict.fromkeys(user_ids, Decimal("0"))
    expense_by_user = dict.fromkeys(user_ids, Decimal("0"))
    recurring_by_user = dict.fromkeys(user_ids, Decimal("0"))
    recurring_count_by_user = dict.fromkeys(user_ids, 0)
    count_by_user = dict.fromkeys(user_ids, 0)
    receipt_count_by_user = dict.fromkeys(user_ids, 0)
    latest_by_user: dict[UUID, Transaction | None] = dict.fromkeys(user_ids, None)
    # Per-member expense category breakdown — keyed by user_id then category_id.
    expense_by_category: dict[UUID, dict[UUID | None, Decimal]] = {
        user_id: {} for user_id in user_ids
    }

    for transaction in transactions:
        occurred_at = _as_aware_utc(transaction.occurred_at).astimezone(ISTANBUL)
        if occurred_at < period_start:
            continue
        amount = Decimal(transaction.amount)
        count_by_user[transaction.user_id] += 1
        if transaction.source == "receipt_ocr":
            receipt_count_by_user[transaction.user_id] += 1
        latest = latest_by_user[transaction.user_id]
        if latest is None or _as_aware_utc(transaction.occurred_at) > _as_aware_utc(
            latest.occurred_at,
        ):
            latest_by_user[transaction.user_id] = transaction
        if transaction.type == "income":
            income_by_user[transaction.user_id] += amount
        else:
            expense_by_user[transaction.user_id] += amount
            bucket = expense_by_category[transaction.user_id]
            bucket[transaction.category_id] = (
                bucket.get(transaction.category_id, Decimal("0")) + amount
            )

    for subscription in subscriptions:
        if subscription.type != "expense":
            continue
        recurring_by_user[subscription.user_id] += monthly_equivalent(
            Decimal(subscription.amount),
            subscription.recurrence_interval,
            subscription.recurrence_unit,
            subscription.billing_cycle,
        )
        recurring_count_by_user[subscription.user_id] += 1

    total_expense = sum(expense_by_user.values(), Decimal("0"))

    # Look up category names once for any category id we actually used.
    used_category_ids: set[UUID] = set()
    for buckets in expense_by_category.values():
        for category_id in buckets:
            if category_id is not None:
                used_category_ids.add(category_id)
    category_name_by_id: dict[UUID, str] = {}
    if used_category_ids:
        rows = db.execute(
            select(Category.id, Category.name).where(
                Category.id.in_(used_category_ids),
                or_(Category.user_id.in_(user_ids), Category.user_id.is_(None)),
            ),
        ).all()
        category_name_by_id = {row.id: row.name for row in rows}

    def build_category_breakdown(
        user_id: UUID, total_for_user: Decimal
    ) -> list[FamilyMemberCategoryBreakdown]:
        buckets = expense_by_category.get(user_id, {})
        if not buckets or total_for_user <= 0:
            return []
        top_n = 4
        sorted_items = sorted(buckets.items(), key=lambda item: item[1], reverse=True)
        head = sorted_items[:top_n]
        tail = sorted_items[top_n:]
        breakdown: list[FamilyMemberCategoryBreakdown] = []
        for category_id, amount in head:
            breakdown.append(
                FamilyMemberCategoryBreakdown(
                    category_id=category_id,
                    category_name=(
                        category_name_by_id.get(category_id, "Kategorisiz")
                        if category_id is not None
                        else "Kategorisiz"
                    ),
                    amount=_money(amount),
                    share_percent=_percent(amount, total_for_user),
                ),
            )
        if tail:
            other_amount = sum((amount for _, amount in tail), Decimal("0"))
            breakdown.append(
                FamilyMemberCategoryBreakdown(
                    category_id=None,
                    category_name="Diğer",
                    amount=_money(other_amount),
                    share_percent=_percent(other_amount, total_for_user),
                ),
            )
        return breakdown

    member_rows: list[FamilyMemberFinanceRead] = []
    for member in members:
        latest = latest_by_user[member.id]
        latest_at = (
            _as_aware_utc(latest.occurred_at).astimezone(ISTANBUL) if latest is not None else None
        )
        member_rows.append(
            FamilyMemberFinanceRead(
                user_id=member.id,
                name=member.name,
                role="parent" if member.role == "parent" else "child",
                birth_date=member.birth_date,
                age=member.age,
                age_status=member.age_status,
                income=_money(income_by_user[member.id]),
                expense=_money(expense_by_user[member.id]),
                balance=_money(income_by_user[member.id] - expense_by_user[member.id]),
                expense_share_percent=_percent(expense_by_user[member.id], total_expense),
                recurring_monthly=_money(recurring_by_user[member.id]),
                recurring_count=recurring_count_by_user[member.id],
                transaction_count=count_by_user[member.id],
                receipt_transaction_count=receipt_count_by_user[member.id],
                latest_transaction_at=latest_at,
                latest_transaction_merchant=(latest.merchant if latest is not None else None),
                latest_transaction_amount=(
                    _money(Decimal(latest.amount)) if latest is not None else None
                ),
                latest_transaction_type=(latest.type if latest is not None else None),
                category_breakdown=build_category_breakdown(
                    member.id,
                    expense_by_user[member.id],
                ),
            ),
        )

    total_income = sum((row.income for row in member_rows), Decimal("0"))
    total_expense = sum((row.expense for row in member_rows), Decimal("0"))
    total_recurring = sum((row.recurring_monthly for row in member_rows), Decimal("0"))
    return FamilyOverviewRead(
        period_start=period_start,
        period_end=now,
        total_income=_money(total_income),
        total_expense=_money(total_expense),
        total_balance=_money(total_income - total_expense),
        total_recurring_monthly=_money(total_recurring),
        members=member_rows,
    )


@router.post("/children", response_model=FamilyMemberRead, status_code=status.HTTP_201_CREATED)
def create_child(
    payload: ChildCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    _ensure_parent(current_user)
    family_id = _ensure_family_id(current_user)
    child = User(
        email=_child_email(current_user),
        name=payload.name,
        role="child",
        parent_id=current_user.id,
        family_id=family_id,
        password_hash=None,
        birth_date=payload.birth_date,
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


@router.delete("/children/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child(
    child_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _ensure_parent(current_user)
    child = _get_child(child_id, current_user, db)
    db.delete(child)
    db.commit()


@router.post("/switch/{child_id}", response_model=TokenResponse)
def switch_to_child(
    child_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    _ensure_parent(current_user)
    child = _get_child(child_id, current_user, db)
    return _token_response(child)
