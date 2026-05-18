"""Service functions for smart saving goals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.saving_goal import SavingGoal
from app.models.transaction import Transaction
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.schemas.saving_goal import SavingGoalProgressRead, SavingGoalRead, SavingGoalUpdate
from app.utils.tl_format import format_tl

ISTANBUL = ZoneInfo("Europe/Istanbul")
MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.1")


@dataclass(frozen=True)
class SavingGoalDraft:
    category: Category
    baseline_amount: Decimal
    target_spending_amount: Decimal
    target_saving_amount: Decimal
    start_date: datetime
    end_date: datetime
    title: str
    strategy: dict[str, object]


@dataclass(frozen=True)
class AccumulationGoalDraft:
    target_amount: Decimal
    current_amount: Decimal
    monthly_contribution: Decimal
    start_date: datetime
    end_date: datetime
    title: str
    strategy: dict[str, object]


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _percent(value: Decimal) -> Decimal:
    return value.quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _month_range(now: datetime) -> tuple[datetime, datetime]:
    local_now = _aware_utc(now).astimezone(ISTANBUL)
    start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.astimezone(UTC), end.astimezone(UTC)


def _serialize_goal(goal: SavingGoal, category_name: str) -> SavingGoalRead:
    return SavingGoalRead(
        id=goal.id,
        user_id=goal.user_id,
        goal_type=goal.goal_type,
        category_id=goal.category_id,
        category_name=category_name,
        title=goal.title,
        baseline_amount=_money(Decimal(goal.baseline_amount)),
        target_spending_amount=_money(Decimal(goal.target_spending_amount)),
        target_saving_amount=_money(Decimal(goal.target_saving_amount)),
        target_amount=_money(Decimal(goal.target_amount))
        if goal.target_amount is not None
        else None,
        current_amount=_money(Decimal(goal.current_amount)),
        monthly_contribution=(
            _money(Decimal(goal.monthly_contribution))
            if goal.monthly_contribution is not None
            else None
        ),
        start_date=goal.start_date,
        end_date=goal.end_date,
        status=goal.status,
        strategy=goal.strategy,
        created_by=goal.created_by,
    )


def _category_name(db: Session, category_id: UUID | None) -> str:
    if category_id is None:
        return "Kategorisiz"
    category = db.execute(select(Category).where(Category.id == category_id)).scalar_one_or_none()
    return category.name if category is not None else "Kategorisiz"


def _normalize_category_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def _category_priority(category: Category, current_user: User) -> tuple[int, str]:
    if category.user_id == current_user.id:
        owner_priority = 0
    elif category.user_id is None:
        owner_priority = 1
    else:
        owner_priority = 2
    return owner_priority, category.name.casefold()


def resolve_goal_category(
    db: Session,
    current_user: User,
    *,
    category_id: UUID | None = None,
    category_name: str | None = None,
    spending_start: datetime | None = None,
    spending_end: datetime | None = None,
) -> Category | None:
    user_ids = visible_user_ids(current_user)
    query = select(Category).where(or_(Category.user_id.in_(user_ids), Category.user_id.is_(None)))
    if category_id is not None:
        query = query.where(Category.id == category_id)
        return db.execute(query).scalar_one_or_none()
    elif category_name is not None:
        searched_name = " ".join(category_name.split())
        normalized_name = searched_name.casefold()
        if not normalized_name:
            return None
        query = query.where(Category.name.ilike(searched_name))
    else:
        return None
    categories = [
        category
        for category in db.execute(query).scalars().all()
        if _normalize_category_name(category.name) == normalized_name
    ]
    if not categories:
        return None
    if spending_start is not None and spending_end is not None:
        categories_with_spending = [
            (
                category,
                _spending_total(
                    db,
                    user_ids=user_ids,
                    category_id=category.id,
                    start_date=spending_start,
                    end_date=spending_end,
                ),
            )
            for category in categories
        ]
        spent_categories = [item for item in categories_with_spending if item[1] > 0]
        if spent_categories:
            return sorted(
                spent_categories,
                key=lambda item: (-item[1], _category_priority(item[0], current_user)),
            )[0][0]
    return sorted(categories, key=lambda category: _category_priority(category, current_user))[0]


def _spending_total(
    db: Session,
    *,
    user_ids: list[UUID],
    category_id: UUID | None,
    start_date: datetime,
    end_date: datetime,
) -> Decimal:
    rows = (
        db.execute(
            select(Transaction).where(
                Transaction.user_id.in_(user_ids),
                Transaction.category_id == category_id,
                Transaction.type == "expense",
                Transaction.occurred_at >= start_date,
                Transaction.occurred_at < end_date,
            ),
        )
        .scalars()
        .all()
    )
    return _money(sum((Decimal(row.amount) for row in rows), Decimal("0")))


def _goal_spending_user_ids(db: Session, goal: SavingGoal) -> list[UUID]:
    owner = db.execute(select(User).where(User.id == goal.user_id)).scalar_one_or_none()
    if owner is None:
        return [goal.user_id]
    return visible_user_ids(owner)


def _tactics(category_name: str, weekly_limit: Decimal) -> list[str]:
    normalized = category_name.casefold()
    first = f"Haftalık üst limitini yaklaşık {format_tl(weekly_limit)} olarak takip et."
    if "market" in normalized:
        return [
            first,
            "Alışverişten önce liste yap ve liste dışı ürünleri bir sonraki haftaya bırak.",
            "Aynı üründe muadil marka fiyatını karşılaştır.",
            "Küçük market alışverişlerini haftada tek büyük alışverişte birleştirmeyi dene.",
        ]
    if "fatura" in normalized:
        return [
            first,
            "Kullanmadığın paket, ek servis veya otomatik yenilemeyi kontrol et.",
            "Elektrik ve su tüketiminde haftalık küçük takip notu tut.",
            "Son ödeme tarihinden önce ödeme planı yaparak gecikme masrafından kaçın.",
        ]
    if "ulaş" in normalized or "ulas" in normalized:
        return [
            first,
            "Yakın mesafelerde tek seferlik taksi yerine toplu taşıma alternatifini karşılaştır.",
            "Haftalık yolculukları önceden planlayıp gereksiz ekstra gidişleri azalt.",
            "Aynı rota için abonman veya çoklu biniş avantajını kontrol et.",
        ]
    return [
        first,
        "Harcama yapmadan önce bu kalem gerçekten bu hafta gerekli mi diye kısa bir kontrol yap.",
        "Benzer harcamaları tek günde toplayıp toplam limiti daha görünür hale getir.",
        "Hafta sonunda gerçekleşen tutarı hedefle karşılaştırıp bir sonraki hafta limitini güncelle.",
    ]


def build_saving_goal_draft(
    db: Session,
    current_user: User,
    *,
    category_id: UUID | None = None,
    category_name: str | None = None,
    target_reduction_percent: Decimal = Decimal("15"),
    baseline_amount: Decimal | None = None,
    now: datetime | None = None,
) -> SavingGoalDraft:
    period_end = _aware_utc(now or datetime.now(UTC))
    period_start = period_end - timedelta(days=30)
    category = resolve_goal_category(
        db,
        current_user,
        category_id=category_id,
        category_name=category_name,
        spending_start=period_start,
        spending_end=period_end,
    )
    if category is None:
        raise ValueError("Kategori bulunamadı.")

    baseline = _money(
        Decimal(baseline_amount)
        if baseline_amount is not None
        else _spending_total(
            db,
            user_ids=visible_user_ids(current_user),
            category_id=category.id,
            start_date=period_start,
            end_date=period_end,
        )
    )
    if baseline <= 0:
        raise ValueError("Bu kategori için hedef önermek üzere son 30 günde gider bulunamadı.")

    reduction = min(max(Decimal(target_reduction_percent), Decimal("1")), Decimal("50"))
    target_spending = _money(baseline * (Decimal("100") - reduction) / Decimal("100"))
    target_saving = _money(baseline - target_spending)
    start_date, end_date = _month_range(period_end)
    weekly_limit = _money(target_spending / Decimal("4"))
    tactics = _tactics(category.name, weekly_limit)
    return SavingGoalDraft(
        category=category,
        baseline_amount=baseline,
        target_spending_amount=target_spending,
        target_saving_amount=target_saving,
        start_date=start_date,
        end_date=end_date,
        title=f"{category.name} harcamamı azalt",
        strategy={
            "reduction_percent": f"{_percent(reduction):.1f}",
            "weekly_limit": f"{weekly_limit:.2f}",
            "weekly_limit_formatted": format_tl(weekly_limit),
            "tactics": tactics,
        },
    )


def create_saving_goal(
    db: Session,
    current_user: User,
    *,
    category_id: UUID | None = None,
    category_name: str | None = None,
    target_reduction_percent: Decimal = Decimal("15"),
    baseline_amount: Decimal | None = None,
    title: str | None = None,
    created_by: str = "manual",
    now: datetime | None = None,
) -> SavingGoal:
    draft = build_saving_goal_draft(
        db,
        current_user,
        category_id=category_id,
        category_name=category_name,
        target_reduction_percent=target_reduction_percent,
        baseline_amount=baseline_amount,
        now=now,
    )
    goal = SavingGoal(
        user_id=current_user.id,
        goal_type="expense_reduction",
        category_id=draft.category.id,
        title=title or draft.title,
        baseline_amount=draft.baseline_amount,
        target_spending_amount=draft.target_spending_amount,
        target_saving_amount=draft.target_saving_amount,
        target_amount=None,
        current_amount=Decimal("0"),
        monthly_contribution=None,
        start_date=draft.start_date,
        end_date=draft.end_date,
        status="active",
        strategy=draft.strategy,
        created_by=created_by,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def _accumulation_tactics(monthly_contribution: Decimal, remaining_amount: Decimal) -> list[str]:
    return [
        f"Aylık hedef katkıyı yaklaşık {format_tl(monthly_contribution)} olarak ayrı bir zarf gibi takip et.",
        "Gelir geldiği gün küçük bir otomatik ayırma hatırlatıcısı kurmayı düşünebilirsin.",
        f"Kalan tutarı ({format_tl(remaining_amount)}) haftalık küçük parçalara bölerek görünür tut.",
        "Bu hedef yatırım tavsiyesi değildir; sadece bütçe içinde ayrılacak tutarı planlar.",
    ]


def _refresh_accumulation_strategy(goal: SavingGoal) -> None:
    target_amount = _money(Decimal(goal.target_amount or goal.target_saving_amount))
    current_amount = _money(Decimal(goal.current_amount))
    monthly_contribution = _money(Decimal(goal.monthly_contribution or Decimal("0")))
    remaining_amount = _money(max(target_amount - current_amount, Decimal("0")))
    existing: dict[str, object] = goal.strategy if isinstance(goal.strategy, dict) else {}
    goal.strategy = {
        **existing,
        "remaining_amount": f"{remaining_amount:.2f}",
        "remaining_amount_formatted": format_tl(remaining_amount),
        "monthly_contribution": f"{monthly_contribution:.2f}",
        "monthly_contribution_formatted": format_tl(monthly_contribution),
        "tactics": _accumulation_tactics(monthly_contribution, remaining_amount),
    }


def build_accumulation_goal_draft(
    *,
    target_amount: Decimal,
    current_amount: Decimal = Decimal("0"),
    monthly_contribution: Decimal | None = None,
    target_date: datetime,
    title: str | None = None,
    now: datetime | None = None,
) -> AccumulationGoalDraft:
    start_date = _aware_utc(now or datetime.now(UTC))
    end_date = _aware_utc(target_date)
    target = _money(Decimal(target_amount))
    current = _money(Decimal(current_amount))
    if target <= 0:
        raise ValueError("Hedef tutar sıfırdan büyük olmalı.")
    if current < 0:
        raise ValueError("Başlangıç tutarı negatif olamaz.")
    if current >= target:
        raise ValueError("Başlangıç tutarı hedef tutardan küçük olmalı.")
    if end_date <= start_date:
        raise ValueError("Hedef tarihi bugünden sonra olmalı.")

    remaining = _money(target - current)
    total_days = Decimal(max((end_date - start_date).days, 1))
    month_count = max(
        (total_days / Decimal("30")).quantize(Decimal("1"), rounding=ROUND_HALF_UP), Decimal("1")
    )
    contribution = _money(
        Decimal(monthly_contribution)
        if monthly_contribution is not None
        else remaining / month_count
    )
    if contribution <= 0:
        raise ValueError("Aylık katkı sıfırdan büyük olmalı.")
    tactics = _accumulation_tactics(contribution, remaining)
    return AccumulationGoalDraft(
        target_amount=target,
        current_amount=current,
        monthly_contribution=contribution,
        start_date=start_date,
        end_date=end_date,
        title=title or "Birikim hedefi",
        strategy={
            "remaining_amount": f"{remaining:.2f}",
            "remaining_amount_formatted": format_tl(remaining),
            "monthly_contribution": f"{contribution:.2f}",
            "monthly_contribution_formatted": format_tl(contribution),
            "tactics": tactics,
        },
    )


def create_accumulation_goal(
    db: Session,
    current_user: User,
    *,
    target_amount: Decimal,
    current_amount: Decimal = Decimal("0"),
    monthly_contribution: Decimal | None = None,
    target_date: datetime,
    title: str | None = None,
    created_by: str = "manual",
    now: datetime | None = None,
) -> SavingGoal:
    draft = build_accumulation_goal_draft(
        target_amount=target_amount,
        current_amount=current_amount,
        monthly_contribution=monthly_contribution,
        target_date=target_date,
        title=title,
        now=now,
    )
    goal = SavingGoal(
        user_id=current_user.id,
        goal_type="accumulation",
        category_id=None,
        title=draft.title,
        baseline_amount=draft.current_amount,
        target_spending_amount=draft.target_amount,
        target_saving_amount=_money(draft.target_amount - draft.current_amount),
        target_amount=draft.target_amount,
        current_amount=draft.current_amount,
        monthly_contribution=draft.monthly_contribution,
        start_date=draft.start_date,
        end_date=draft.end_date,
        status="active",
        strategy=draft.strategy,
        created_by=created_by,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def find_active_saving_goal(
    db: Session,
    current_user: User,
    *,
    category_name: str | None = None,
) -> SavingGoal | None:
    query = select(SavingGoal).where(
        SavingGoal.user_id.in_(visible_user_ids(current_user)),
        SavingGoal.status == "active",
    )
    if category_name is not None:
        category = resolve_goal_category(db, current_user, category_name=category_name)
        if category is None:
            return None
        query = query.where(SavingGoal.category_id == category.id)
    return db.execute(query.order_by(SavingGoal.created_at.desc())).scalar_one_or_none()


def update_saving_goal(db: Session, goal: SavingGoal, payload: SavingGoalUpdate) -> SavingGoal:
    if payload.title is not None:
        goal.title = payload.title
    if payload.status is not None:
        goal.status = payload.status

    updates_accumulation_amount = (
        payload.current_amount is not None
        or payload.contribution_amount is not None
        or payload.monthly_contribution is not None
    )
    if updates_accumulation_amount and goal.goal_type != "accumulation":
        raise ValueError("Katkı ve birikim tutarı yalnızca birikim hedefinde güncellenebilir.")
    if updates_accumulation_amount and goal.status != "active":
        raise ValueError("Aktif olmayan hedefe katkı eklenemez.")

    if goal.goal_type == "accumulation":
        target_amount = _money(Decimal(goal.target_amount or goal.target_saving_amount))
        next_current = _money(Decimal(goal.current_amount))
        if payload.current_amount is not None:
            next_current = _money(Decimal(payload.current_amount))
        if payload.contribution_amount is not None:
            next_current = _money(next_current + Decimal(payload.contribution_amount))
        if next_current > target_amount:
            raise ValueError("Birikim tutarı hedef tutarı aşamaz.")
        goal.current_amount = next_current
        if payload.monthly_contribution is not None:
            goal.monthly_contribution = _money(Decimal(payload.monthly_contribution))
        if next_current >= target_amount:
            goal.status = "completed"
        _refresh_accumulation_strategy(goal)

    db.commit()
    db.refresh(goal)
    return goal


def serialize_saving_goal(db: Session, goal: SavingGoal) -> SavingGoalRead:
    if goal.goal_type == "accumulation":
        return _serialize_goal(goal, "Birikim")
    return _serialize_goal(goal, _category_name(db, goal.category_id))


def calculate_saving_goal_progress(
    db: Session,
    goal: SavingGoal,
    *,
    now: datetime | None = None,
) -> SavingGoalProgressRead:
    period_now = _aware_utc(now or datetime.now(UTC))
    if goal.goal_type == "accumulation":
        target_amount = _money(Decimal(goal.target_amount or goal.target_saving_amount))
        start_amount = _money(Decimal(goal.baseline_amount))
        current_amount = _money(Decimal(goal.current_amount))
        remaining_amount = _money(max(target_amount - current_amount, Decimal("0")))
        progress_percent = (
            Decimal("0")
            if target_amount == 0
            else _percent((current_amount / target_amount) * Decimal("100"))
        )
        total_seconds = max(
            (_aware_utc(goal.end_date) - _aware_utc(goal.start_date)).total_seconds(), 1
        )
        elapsed_seconds = min(
            max((period_now - _aware_utc(goal.start_date)).total_seconds(), 0),
            total_seconds,
        )
        expected_amount = _money(
            start_amount
            + (target_amount - start_amount) * Decimal(str(elapsed_seconds / total_seconds))
        )
        if goal.status == "completed" or current_amount >= target_amount:
            status_label = "completed"
        elif current_amount < expected_amount:
            status_label = "at_risk"
        else:
            status_label = "on_track"
        tactics = []
        if isinstance(goal.strategy, dict) and isinstance(goal.strategy.get("tactics"), list):
            tactics = [str(item) for item in goal.strategy["tactics"][:4]]
        if not tactics:
            monthly = _money(Decimal(goal.monthly_contribution or Decimal("0")))
            tactics = _accumulation_tactics(monthly, remaining_amount)
        serialized = _serialize_goal(goal, "Birikim")
        return SavingGoalProgressRead(
            goal=serialized,
            actual_spending=Decimal("0.00"),
            saved_amount=current_amount,
            remaining_limit=remaining_amount,
            remaining_amount=remaining_amount,
            progress_percent=progress_percent,
            expected_spending_to_date=expected_amount,
            status_label=status_label,
            tactics=tactics,
        )

    actual = _spending_total(
        db,
        user_ids=_goal_spending_user_ids(db, goal),
        category_id=goal.category_id,
        start_date=_aware_utc(goal.start_date),
        end_date=min(period_now, _aware_utc(goal.end_date)),
    )
    baseline = Decimal(goal.baseline_amount)
    target_spending = Decimal(goal.target_spending_amount)
    target_saving = Decimal(goal.target_saving_amount)
    saved = _money(baseline - actual)
    remaining_limit = _money(target_spending - actual)
    progress_percent = (
        Decimal("0") if target_saving == 0 else _percent((saved / target_saving) * Decimal("100"))
    )

    total_seconds = max(
        (_aware_utc(goal.end_date) - _aware_utc(goal.start_date)).total_seconds(), 1
    )
    elapsed_seconds = min(
        max((period_now - _aware_utc(goal.start_date)).total_seconds(), 0),
        total_seconds,
    )
    expected_spending = _money(target_spending * Decimal(str(elapsed_seconds / total_seconds)))
    if goal.status == "completed":
        status_label = "completed"
    elif actual > target_spending:
        status_label = "over_limit"
    elif actual > expected_spending:
        status_label = "at_risk"
    else:
        status_label = "on_track"

    category_name = _category_name(db, goal.category_id)
    tactics = []
    if isinstance(goal.strategy, dict) and isinstance(goal.strategy.get("tactics"), list):
        tactics = [str(item) for item in goal.strategy["tactics"][:4]]
    if not tactics:
        tactics = _tactics(category_name, _money(target_spending / Decimal("4")))

    return SavingGoalProgressRead(
        goal=_serialize_goal(goal, category_name),
        actual_spending=actual,
        saved_amount=saved,
        remaining_limit=remaining_limit,
        remaining_amount=remaining_limit,
        progress_percent=progress_percent,
        expected_spending_to_date=expected_spending,
        status_label=status_label,
        tactics=tactics,
    )
