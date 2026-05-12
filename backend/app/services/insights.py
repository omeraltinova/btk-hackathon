"""Proactive insight generation from scoped financial data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.insight import ProactiveInsight
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.utils.tl_format import format_tl

ISTANBUL = ZoneInfo("Europe/Istanbul")


@dataclass(frozen=True)
class InsightCandidate:
    user_id: UUID
    insight_type: str
    title: str
    content: str
    severity: str = "info"
    action_label: str | None = None


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _previous_month_start(value: datetime) -> datetime:
    if value.month == 1:
        return value.replace(year=value.year - 1, month=12)
    return value.replace(month=value.month - 1)


def _monthly_equivalent(amount: Decimal, cycle: str) -> Decimal:
    if cycle == "weekly":
        return amount * Decimal("4")
    if cycle == "yearly":
        return amount / Decimal("12")
    return amount


def _category_names(categories: list[Category]) -> dict[UUID | None, str]:
    return {category.id: category.name for category in categories}


def build_insight_candidates(
    db: Session,
    current_user: User,
    *,
    now: datetime | None = None,
) -> list[InsightCandidate]:
    user_ids = visible_user_ids(current_user)
    period_end = _aware_utc(now or datetime.now(UTC)).astimezone(ISTANBUL)
    current_start = _month_start(period_end)
    previous_start = _previous_month_start(current_start)
    stale_cutoff = period_end - timedelta(days=30)

    categories = list(
        db.execute(
            select(Category).where(Category.user_id.in_(user_ids) | Category.user_id.is_(None))
        )
        .scalars()
        .all(),
    )
    category_names = _category_names(categories)
    transactions = list(
        db.execute(
            select(Transaction).where(
                Transaction.user_id.in_(user_ids),
                Transaction.occurred_at >= previous_start.astimezone(UTC),
            ),
        )
        .scalars()
        .all(),
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

    candidates: list[InsightCandidate] = []
    if not any(_aware_utc(tx.occurred_at) >= stale_cutoff.astimezone(UTC) for tx in transactions):
        candidates.append(
            InsightCandidate(
                user_id=current_user.id,
                insight_type="low_activity",
                title="Defter sessiz kalmış",
                content=(
                    "Son 30 günde kayıtlı gelir veya gider görünmüyor. Birkaç gerçek işlem "
                    "eklediğinde koç daha isabetli uyarılar üretebilir."
                ),
                action_label="İşlem ekle",
            ),
        )
        return candidates

    current_income = Decimal("0")
    current_expense = Decimal("0")
    previous_category_totals: dict[UUID | None, Decimal] = {}
    current_category_totals: dict[UUID | None, Decimal] = {}
    receipt_count = 0

    for transaction in transactions:
        occurred_at = _aware_utc(transaction.occurred_at).astimezone(ISTANBUL)
        amount = Decimal(transaction.amount)
        if transaction.source == "receipt_ocr":
            receipt_count += 1
        if occurred_at >= current_start:
            if transaction.type == "income":
                current_income += amount
            else:
                current_expense += amount
                current_category_totals[transaction.category_id] = (
                    current_category_totals.get(transaction.category_id, Decimal("0")) + amount
                )
        elif occurred_at >= previous_start and transaction.type == "expense":
            previous_category_totals[transaction.category_id] = (
                previous_category_totals.get(transaction.category_id, Decimal("0")) + amount
            )

    balance = current_income - current_expense
    candidates.append(
        InsightCandidate(
            user_id=current_user.id,
            insight_type="monthly_status",
            title="Aylık durum özeti hazır",
            content=(
                f"Bu ay gelir {format_tl(current_income)}, gider {format_tl(current_expense)}. "
                f"Net durum {format_tl(balance)}."
            ),
            severity="warning" if balance < 0 else "info",
            action_label="Paneli incele",
        ),
    )

    for category_id, current_amount in current_category_totals.items():
        previous_amount = previous_category_totals.get(category_id, Decimal("0"))
        if previous_amount > 0 and current_amount > previous_amount * Decimal("1.25"):
            name = category_names.get(category_id, "Kategorisiz")
            candidates.append(
                InsightCandidate(
                    user_id=current_user.id,
                    insight_type="spending_spike",
                    title=f"{name} harcamasında artış var",
                    content=(
                        f"Bu ay {name} harcaması {format_tl(current_amount)}. "
                        f"Geçen ay aynı döneme göre {format_tl(previous_amount)} seviyesindeydi."
                    ),
                    severity="warning",
                    action_label="Detaya bak",
                ),
            )

    for category in categories:
        if category.budget_monthly is None:
            continue
        spent = current_category_totals.get(category.id, Decimal("0"))
        if spent > Decimal(category.budget_monthly):
            candidates.append(
                InsightCandidate(
                    user_id=current_user.id,
                    insight_type="category_overspending",
                    title=f"{category.name} bütçesi aşıldı",
                    content=(
                        f"Aylık hedef {format_tl(Decimal(category.budget_monthly))}, "
                        f"şu anki harcama {format_tl(spent)}."
                    ),
                    severity="critical",
                    action_label="Kategoriye bak",
                ),
            )

    today = period_end.date()
    upcoming = [
        subscription
        for subscription in subscriptions
        if subscription.next_billing_date
        and today <= subscription.next_billing_date <= today + timedelta(days=7)
    ]
    for subscription in upcoming[:2]:
        next_billing_date = subscription.next_billing_date
        if next_billing_date is None:
            continue
        candidates.append(
            InsightCandidate(
                user_id=subscription.user_id,
                insight_type="upcoming_recurring",
                title=f"{subscription.name} yaklaşıyor",
                content=(
                    f"{next_billing_date.strftime('%d.%m.%Y')} tarihinde "
                    f"{format_tl(Decimal(subscription.amount))} ödeme görünüyor."
                ),
                severity="warning",
                action_label="Tekrarları aç",
            ),
        )

    monthly_subscriptions = sum(
        (_monthly_equivalent(Decimal(item.amount), item.billing_cycle) for item in subscriptions),
        Decimal("0"),
    )
    if current_income > 0 and monthly_subscriptions > current_income * Decimal("0.10"):
        candidates.append(
            InsightCandidate(
                user_id=current_user.id,
                insight_type="savings_opportunity",
                title="Tekrarlayan ödemeler dikkat istiyor",
                content=(
                    f"Aktif tekrarlayan ödemelerin aylık etkisi {format_tl(monthly_subscriptions)}. "
                    "Bu tutar gelirinin %10'unu aşıyor."
                ),
                action_label="Tekrarları gözden geçir",
            ),
        )

    if receipt_count > 0:
        candidates.append(
            InsightCandidate(
                user_id=current_user.id,
                insight_type="receipt_activity",
                title="Fişler bütçeye dahil oldu",
                content=f"Bu ay {receipt_count} fiş kaynaklı işlem bütçeye yansıdı.",
                action_label="Fişleri aç",
            ),
        )

    return candidates[:6]


def refresh_insights_for_user(
    db: Session,
    current_user: User,
    *,
    now: datetime | None = None,
) -> list[ProactiveInsight]:
    user_ids = visible_user_ids(current_user)
    existing = list(
        db.execute(
            select(ProactiveInsight).where(
                ProactiveInsight.user_id.in_(user_ids),
                ProactiveInsight.is_dismissed.is_(False),
            ),
        )
        .scalars()
        .all(),
    )
    for insight in existing:
        insight.is_dismissed = True

    generated = [
        ProactiveInsight(
            user_id=candidate.user_id,
            insight_type=candidate.insight_type,
            title=candidate.title,
            content=candidate.content,
            severity=candidate.severity,
            action_label=candidate.action_label,
            is_dismissed=False,
        )
        for candidate in build_insight_candidates(db, current_user, now=now)
    ]
    db.add_all(generated)
    db.commit()
    for insight in generated:
        db.refresh(insight)
    return generated


def list_active_insights(db: Session, current_user: User) -> list[ProactiveInsight]:
    user_ids = visible_user_ids(current_user)
    insights = list(
        db.execute(
            select(ProactiveInsight)
            .where(
                ProactiveInsight.user_id.in_(user_ids),
                ProactiveInsight.is_dismissed.is_(False),
            )
            .order_by(ProactiveInsight.created_at.desc()),
        )
        .scalars()
        .all(),
    )
    if insights:
        return insights
    return refresh_insights_for_user(db, current_user)
