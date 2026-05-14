"""Smart goal planning from scoped spending and subscription data."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.saving_goal import SavingGoal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.services.saving_goals import (
    calculate_saving_goal_progress,
    create_accumulation_goal,
    create_saving_goal,
)
from app.utils.recurrence import monthly_equivalent
from app.utils.tl_format import format_tl

MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.1")
EXCLUDED_CATEGORY_NAMES = {"birikim", "gelir"}


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _decimal_text(value: Decimal) -> str:
    return f"{_money(value):.2f}"


def _percent(value: Decimal) -> Decimal:
    return value.quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _target_amount_from_message(message: str) -> Decimal | None:
    matches = re.findall(r"\d[\d\.]*,?\d*", message)
    if not matches:
        return None
    amounts: list[Decimal] = []
    for match in matches:
        raw = match.replace(".", "").replace(",", ".")
        try:
            amount = Decimal(raw)
        except InvalidOperation:
            continue
        if amount >= Decimal("100"):
            amounts.append(amount)
    if not amounts:
        return None
    amount = max(amounts)
    return _money(amount) if amount > 0 else None


def _goal_label_from_message(message: str) -> str:
    normalized = message.casefold()
    if "tatil" in normalized:
        return "Tatil"
    if "telefon" in normalized:
        return "Telefon"
    if "okul" in normalized or "eğitim" in normalized or "egitim" in normalized:
        return "Eğitim"
    return "Birikim"


def _target_months_from_message(message: str) -> int:
    normalized = message.casefold()
    month_match = re.search(r"(\d{1,3})\s*(?:ay|ayda|aylık|aylik)", normalized)
    if month_match:
        return max(1, min(int(month_match.group(1)), 120))
    year_match = re.search(r"(\d{1,2})\s*(?:yıl|yil|senede|sene)", normalized)
    if year_match:
        return max(1, min(int(year_match.group(1)) * 12, 120))
    return 12


def _reduction_percent_for_category(category_name: str) -> Decimal:
    normalized = category_name.casefold()
    if "yemek" in normalized or "eglence" in normalized or "eğlence" in normalized:
        return Decimal("20")
    if "fatura" in normalized or "okul" in normalized or "eğitim" in normalized:
        return Decimal("10")
    return Decimal("15")


def _categories_by_id(categories: list[Category]) -> dict[UUID | None, Category]:
    return {category.id: category for category in categories}


def _find_active_goal_by_category(
    db: Session,
    current_user: User,
    category_id: UUID,
) -> SavingGoal | None:
    return db.execute(
        select(SavingGoal).where(
            SavingGoal.user_id.in_(visible_user_ids(current_user)),
            SavingGoal.status == "active",
            SavingGoal.category_id == category_id,
        ),
    ).scalar_one_or_none()


def build_smart_saving_plan(
    db: Session,
    current_user: User,
    *,
    message: str,
    now: datetime | None = None,
    max_goals: int = 2,
) -> dict[str, object]:
    period_end = _aware_utc(now or datetime.now(UTC))
    period_start = period_end - timedelta(days=30)
    user_ids = visible_user_ids(current_user)
    categories = list(
        db.execute(
            select(Category).where(or_(Category.user_id.in_(user_ids), Category.user_id.is_(None))),
        )
        .scalars()
        .all(),
    )
    category_by_id = _categories_by_id(categories)
    transactions = list(
        db.execute(
            select(Transaction).where(
                Transaction.user_id.in_(user_ids),
                Transaction.type == "expense",
                Transaction.occurred_at >= period_start,
            ),
        )
        .scalars()
        .all(),
    )

    totals_by_category: dict[UUID | None, Decimal] = {}
    total_expense = Decimal("0")
    for transaction in transactions:
        amount = Decimal(transaction.amount)
        total_expense += amount
        totals_by_category[transaction.category_id] = (
            totals_by_category.get(transaction.category_id, Decimal("0")) + amount
        )

    candidates: list[tuple[Category, Decimal]] = []
    for category_id, amount in totals_by_category.items():
        category = category_by_id.get(category_id)
        if category is None or category.name.casefold() in EXCLUDED_CATEGORY_NAMES:
            continue
        if amount <= 0:
            continue
        candidates.append((category, _money(amount)))
    candidates.sort(key=lambda item: item[1], reverse=True)

    created_goals: list[dict[str, object]] = []
    for category, baseline in candidates[:max_goals]:
        reduction_percent = _reduction_percent_for_category(category.name)
        existing = _find_active_goal_by_category(db, current_user, category.id)
        if existing is None:
            goal = create_saving_goal(
                db,
                current_user,
                category_name=category.name,
                target_reduction_percent=reduction_percent,
                baseline_amount=baseline,
                created_by="agent",
                now=period_end,
            )
            created = True
        else:
            goal = existing
            created = False
        progress = calculate_saving_goal_progress(db, goal, now=period_end)
        created_goals.append(
            {
                "goal_id": str(goal.id),
                "category_name": progress.goal.category_name,
                "baseline_amount": _decimal_text(progress.goal.baseline_amount),
                "baseline_amount_formatted": format_tl(progress.goal.baseline_amount),
                "target_spending_amount": _decimal_text(progress.goal.target_spending_amount),
                "target_spending_amount_formatted": format_tl(progress.goal.target_spending_amount),
                "target_saving_amount": _decimal_text(progress.goal.target_saving_amount),
                "target_saving_amount_formatted": format_tl(progress.goal.target_saving_amount),
                "reduction_percent": f"{_percent(reduction_percent):.1f}",
                "created": created,
                "tactics": progress.tactics,
            },
        )

    subscriptions = list(
        db.execute(
            select(Subscription).where(
                Subscription.user_id.in_(user_ids),
                Subscription.is_active.is_(True),
            ),
        )
        .scalars()
        .all(),
    )
    subscription_monthly_total = sum(
        (
            monthly_equivalent(
                Decimal(subscription.amount),
                subscription.recurrence_interval,
                subscription.recurrence_unit,
                subscription.billing_cycle,
            )
            for subscription in subscriptions
        ),
        Decimal("0"),
    )
    target_amount = _target_amount_from_message(message)
    accumulation_goal: dict[str, object] | None = None
    if target_amount is not None:
        target_label = _goal_label_from_message(message)
        accumulation = create_accumulation_goal(
            db,
            current_user,
            target_amount=target_amount,
            target_date=period_end + timedelta(days=30 * _target_months_from_message(message)),
            title=f"{target_label} birikimi",
            created_by="agent",
            now=period_end,
        )
        accumulation_progress = calculate_saving_goal_progress(db, accumulation, now=period_end)
        accumulation_goal = {
            "goal_id": str(accumulation.id),
            "title": accumulation.title,
            "target_amount": _decimal_text(
                accumulation_progress.goal.target_amount or Decimal("0")
            ),
            "target_amount_formatted": format_tl(
                accumulation_progress.goal.target_amount or Decimal("0"),
            ),
            "remaining_amount": _decimal_text(accumulation_progress.remaining_amount),
            "remaining_amount_formatted": format_tl(accumulation_progress.remaining_amount),
            "monthly_contribution": _decimal_text(
                accumulation_progress.goal.monthly_contribution or Decimal("0"),
            ),
            "monthly_contribution_formatted": format_tl(
                accumulation_progress.goal.monthly_contribution or Decimal("0"),
            ),
        }
    expected_monthly_saving = _money(
        sum(
            (Decimal(str(goal["target_saving_amount"])) for goal in created_goals),
            Decimal("0"),
        )
    )
    return {
        "plan_type": "smart_saving_plan",
        "target_label": _goal_label_from_message(message),
        "target_amount": _decimal_text(target_amount) if target_amount is not None else None,
        "target_amount_formatted": format_tl(target_amount) if target_amount is not None else None,
        "accumulation_goal": accumulation_goal,
        "analysis_period_days": 30,
        "total_expense": _decimal_text(total_expense),
        "total_expense_formatted": format_tl(total_expense),
        "created_goal_count": sum(1 for goal in created_goals if goal["created"] is True),
        "goals": created_goals,
        "expected_monthly_saving": _decimal_text(expected_monthly_saving),
        "expected_monthly_saving_formatted": format_tl(expected_monthly_saving),
        "subscription_count": len(subscriptions),
        "subscription_monthly_total": _decimal_text(subscription_monthly_total),
        "subscription_monthly_total_formatted": format_tl(subscription_monthly_total),
        "subscription_note": (
            "Aktif abonelikleri gözden geçirmek ek tasarruf fırsatı sağlayabilir."
            if subscription_monthly_total > 0
            else None
        ),
    }
