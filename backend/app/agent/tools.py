"""Agent tool implementations backed by scoped database queries."""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.memory import AgentMemory
from app.models.message import Message
from app.models.saving_goal import SavingGoal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.routers.categories import create_envelope_category, set_envelope_budget
from app.schemas.saving_goal import SavingGoalProgressRead, SavingGoalStatus, SavingGoalUpdate
from app.services.envelopes import (
    BudgetEnvelope,
    build_envelope_budget_summary,
    custom_envelope_category_id,
    envelope_definition_for_slug,
    resolve_envelope_category,
)
from app.services.image_gen import IllustrationService, IllustrationUnavailableError
from app.services.ocr import ReceiptOcrError, ReceiptOcrService, ReceiptOcrUnavailableError
from app.services.saving_goals import (
    calculate_saving_goal_progress,
    create_accumulation_goal,
    create_saving_goal,
    find_active_saving_goal,
    update_saving_goal,
)
from app.services.smart_plans import build_smart_saving_plan
from app.utils.date_format import format_tr_date
from app.utils.recurrence import monthly_equivalent, recurrence_label
from app.utils.tl_format import format_tl

MONEY_QUANT = Decimal("0.01")
MAX_SPENDING_DAYS = 365
MONTHLY_TREND_MIN_DAYS = 180
MONTHLY_TREND_MAX_SERIES = 5
ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
BLOCKED_ILLUSTRATION_TERMS = (
    "hisse",
    "borsa",
    "kripto",
    "bitcoin",
    "al sat",
    "al-sat",
    "yatırım öner",
    "hangi fon",
    "hangi altın",
    "hangi döviz",
)
BLOCKED_MEMORY_KEYWORDS = (
    "api key",
    "apikey",
    "token",
    "jwt",
    "secret",
    "şifre",
    "sifre",
    "parola",
    "password",
    "iban",
    "kart numarası",
    "kart numarasi",
    "kredi kartı",
    "kredi karti",
    "tc kimlik",
    "tckn",
    "raw ocr",
    "ham ocr",
    "base64",
    "fiş görseli",
    "fis gorseli",
)
IBAN_PATTERN = re.compile(r"\bTR\d{2}[\s-]?(?:\d[\s-]?){20}\d\b", re.IGNORECASE)
CARD_NUMBER_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")
TCKN_PATTERN = re.compile(r"\b\d{11}\b")
BASE64ISH_PATTERN = re.compile(r"\b[A-Za-z0-9+/]{80,}={0,2}\b")
CUSTOM_LESSON_LEVELS = {"child", "beginner", "intermediate", "advanced"}
CUSTOM_LESSON_BLOCKED_ADVICE_PATTERNS = (
    r"\bhangi\b.*\b(hisse|fon|kripto|coin|alt[ıi]n|d[öo]viz)\b",
    r"\b(hisse|fon|kripto|coin|alt[ıi]n|d[öo]viz)\b.*\b(alay[ıi]m|almal[ıi]|satay[ıi]m|satmal[ıi]|öner|oner)\b",
    r"\bgetiri\s+(?:garantisi|vaadi|oran[ıi])\b",
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _decimal_text(value: Decimal) -> str:
    return f"{_money(value):.2f}"


def _fold_control_text(value: object) -> str:
    return (
        " ".join(str(value).casefold().split())
        .replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )


def parse_money_text(value: object) -> Decimal:
    normalized = str(value).replace("₺", "").replace("TL", "").replace("tl", "").strip()
    normalized = re.sub(r"[^\d,.-]", "", normalized)
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    return Decimal(normalized)


def parse_int_text(
    value: object,
    *,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    match = re.search(r"-?\d+", str(value))
    if match is None:
        return default
    parsed = int(match.group(0))
    return max(min_value, min(parsed, max_value))


def parse_bool_text(value: object, *, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    normalized = _fold_control_text(value)
    if normalized in {"false", "0", "hayir", "no", "all", "hepsi"} or any(
        hint in normalized for hint in ("tum", "hepsi", "pasif")
    ):
        return False
    if normalized in {"true", "1", "evet", "yes", "active"} or "aktif" in normalized:
        return True
    return default


def parse_goal_status_text(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = _fold_control_text(value)
    if normalized in {"active"} or any(
        hint in normalized for hint in ("aktif", "suruyor", "surdur", "devam")
    ):
        return "active"
    if normalized in {"paused", "pause"} or any(
        hint in normalized for hint in ("duraklat", "bekle")
    ):
        return "paused"
    if normalized in {"completed", "complete", "done"} or any(
        hint in normalized for hint in ("tamam", "bitti")
    ):
        return "completed"
    return str(value)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalized_days(days: int) -> int:
    return max(1, min(days, MAX_SPENDING_DAYS))


def _normalized_text(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _memory_key_from_text(text: str) -> str:
    words = re.findall(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+", _normalized_text(text))
    slug = "_".join(words[:6])[:48].strip("_")
    return f"note_{slug}" if slug else "note"


def _memory_text_is_safe(text: str) -> bool:
    normalized = _normalized_text(text)
    if any(keyword in normalized for keyword in BLOCKED_MEMORY_KEYWORDS):
        return False
    return not any(
        pattern.search(text)
        for pattern in (IBAN_PATTERN, CARD_NUMBER_PATTERN, TCKN_PATTERN, BASE64ISH_PATTERN)
    )


def _matches_text(known_label: str | None, candidates: Iterable[str]) -> bool:
    known = _normalized_text(known_label)
    if not known:
        return False
    for candidate in candidates:
        normalized = _normalized_text(candidate)
        if normalized and (known in normalized or normalized in known):
            return True
    return False


def _month_start(value: datetime) -> date:
    local = _aware_utc(value).astimezone(ISTANBUL_TZ)
    return date(local.year, local.month, 1)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    return date(value.year + month_index // 12, month_index % 12 + 1, 1)


def _month_label(value: date) -> str:
    return f"{value.month:02d}.{value.year}"


def _month_range(start: datetime, end: datetime) -> list[date]:
    current = _month_start(start)
    final = _month_start(end)
    months: list[date] = []
    while current <= final:
        months.append(current)
        current = _add_months(current, 1)
    return months


def _local_month_start_utc(value: datetime) -> datetime:
    local = _aware_utc(value).astimezone(ISTANBUL_TZ)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def _load_current_user(db: Session, user_id: str) -> User:
    try:
        parsed_user_id = UUID(user_id)
    except ValueError as exc:
        raise ValueError("Geçersiz kullanıcı durumu.") from exc

    user = db.execute(select(User).where(User.id == parsed_user_id)).scalar_one_or_none()
    if user is None:
        raise ValueError("Kullanıcı bulunamadı.")
    return user


def visible_categories(db: Session, current_user: User) -> list[Category]:
    """Return system categories plus categories owned by the visible family scope."""
    user_ids = visible_user_ids(current_user)
    return list(
        db.execute(
            select(Category).where(or_(Category.user_id.in_(user_ids), Category.user_id.is_(None))),
        )
        .scalars()
        .all(),
    )


def infer_category_from_text(db: Session, current_user: User, text: str) -> str | None:
    """Best-effort category extraction for the deterministic Day 3 stream path."""
    envelope_category = resolve_envelope_category(text)
    if envelope_category is not None:
        return envelope_category
    normalized = text.casefold()
    categories = visible_categories(db, current_user)
    for category in sorted(categories, key=lambda item: len(item.name), reverse=True):
        if category.name.casefold() in normalized:
            return category.name
    return None


def build_spending_summary(
    db: Session,
    current_user: User,
    *,
    category: str | None = None,
    days: int = 30,
    now: datetime | None = None,
) -> dict[str, object]:
    """Summarise expenses for the current user's visible family scope."""
    safe_days = _normalized_days(days)
    period_end = _aware_utc(now or datetime.now(UTC))
    period_start = period_end - timedelta(days=safe_days)
    current_month_start = _local_month_start_utc(period_end)
    query_start = min(period_start, current_month_start)
    user_ids = visible_user_ids(current_user)
    categories = visible_categories(db, current_user)
    category_names = {item.id: item.name for item in categories}
    resolved_category = resolve_envelope_category(category) if category else None
    category_name_filter = resolved_category or category
    category_filter = category_name_filter.casefold() if category_name_filter else None

    transactions = list(
        db.execute(
            select(Transaction)
            .where(
                Transaction.user_id.in_(user_ids),
                Transaction.occurred_at >= query_start,
                Transaction.type == "expense",
            )
            .order_by(Transaction.occurred_at.desc()),
        )
        .scalars()
        .all(),
    )

    total = Decimal("0")
    included = 0
    category_totals: dict[str, Decimal] = {}
    current_month_category_totals: dict[UUID | None, Decimal] = {}
    latest_transaction: datetime | None = None

    for transaction in transactions:
        occurred_at = _aware_utc(transaction.occurred_at)
        amount = Decimal(transaction.amount)
        if occurred_at >= current_month_start:
            current_month_category_totals[transaction.category_id] = (
                current_month_category_totals.get(transaction.category_id, Decimal("0")) + amount
            )
        category_name = (
            category_names.get(transaction.category_id, "Kategorisiz")
            if transaction.category_id is not None
            else "Kategorisiz"
        )
        if occurred_at < period_start:
            continue
        if category_filter is not None and category_filter not in category_name.casefold():
            continue
        total += amount
        included += 1
        category_totals[category_name] = category_totals.get(category_name, Decimal("0")) + amount
        if latest_transaction is None or occurred_at > latest_transaction:
            latest_transaction = occurred_at

    rows = [
        {
            "category": name,
            "amount": _decimal_text(amount),
            "amount_formatted": format_tl(amount),
        }
        for name, amount in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
    ]
    budget_summary = build_envelope_budget_summary(
        categories=categories,
        current_category_totals=current_month_category_totals,
        now=period_end,
    )
    matching_envelope = next(
        (
            envelope
            for envelope in budget_summary.envelopes
            if category_name_filter is not None
            and envelope.category_name.casefold() == category_name_filter.casefold()
        ),
        None,
    )
    savings_envelope = next(
        (envelope for envelope in budget_summary.envelopes if envelope.is_savings_goal),
        None,
    )

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_start_formatted": format_tr_date(period_start),
        "period_end_formatted": format_tr_date(period_end),
        "days": safe_days,
        "category": category_name_filter,
        "transaction_count": included,
        "total_amount": _decimal_text(total),
        "total_amount_formatted": format_tl(total),
        "latest_transaction_date": latest_transaction.isoformat() if latest_transaction else None,
        "latest_transaction_date_formatted": (
            format_tr_date(latest_transaction) if latest_transaction else None
        ),
        "category_totals": rows,
        "budget_envelope": None
        if matching_envelope is None or matching_envelope.budget <= 0
        else {
            "slug": matching_envelope.slug,
            "label": matching_envelope.label,
            "category_name": matching_envelope.category_name,
            "budget": _decimal_text(matching_envelope.budget),
            "budget_formatted": format_tl(matching_envelope.budget),
            "spent": _decimal_text(matching_envelope.spent),
            "spent_formatted": format_tl(matching_envelope.spent),
            "remaining": _decimal_text(matching_envelope.remaining),
            "remaining_formatted": format_tl(matching_envelope.remaining),
            "days_left_in_month": matching_envelope.days_left_in_month,
            "safe_daily_amount": _decimal_text(matching_envelope.safe_daily_amount),
            "safe_daily_amount_formatted": format_tl(matching_envelope.safe_daily_amount),
            "status": matching_envelope.status,
            "is_savings_goal": matching_envelope.is_savings_goal,
        },
        "savings_envelope": None
        if savings_envelope is None or savings_envelope.budget <= 0
        else {
            "label": savings_envelope.label,
            "budget": _decimal_text(savings_envelope.budget),
            "budget_formatted": format_tl(savings_envelope.budget),
            "spent": _decimal_text(savings_envelope.spent),
            "spent_formatted": format_tl(savings_envelope.spent),
            "remaining": _decimal_text(savings_envelope.remaining),
            "remaining_formatted": format_tl(savings_envelope.remaining),
        },
    }


def _progress_to_tool_result(progress: SavingGoalProgressRead) -> dict[str, object]:
    goal = progress.goal
    return {
        "goal_id": str(goal.id),
        "goal_type": goal.goal_type,
        "category_id": str(goal.category_id) if goal.category_id is not None else None,
        "category_name": goal.category_name,
        "title": goal.title,
        "baseline_amount": _decimal_text(goal.baseline_amount),
        "baseline_amount_formatted": format_tl(goal.baseline_amount),
        "target_spending_amount": _decimal_text(goal.target_spending_amount),
        "target_spending_amount_formatted": format_tl(goal.target_spending_amount),
        "target_saving_amount": _decimal_text(goal.target_saving_amount),
        "target_saving_amount_formatted": format_tl(goal.target_saving_amount),
        "target_amount": _decimal_text(goal.target_amount)
        if goal.target_amount is not None
        else None,
        "target_amount_formatted": format_tl(goal.target_amount)
        if goal.target_amount is not None
        else None,
        "current_amount": _decimal_text(goal.current_amount),
        "current_amount_formatted": format_tl(goal.current_amount),
        "monthly_contribution": (
            _decimal_text(goal.monthly_contribution)
            if goal.monthly_contribution is not None
            else None
        ),
        "monthly_contribution_formatted": (
            format_tl(goal.monthly_contribution) if goal.monthly_contribution is not None else None
        ),
        "actual_spending": _decimal_text(progress.actual_spending),
        "actual_spending_formatted": format_tl(progress.actual_spending),
        "saved_amount": _decimal_text(progress.saved_amount),
        "saved_amount_formatted": format_tl(progress.saved_amount),
        "remaining_limit": _decimal_text(progress.remaining_limit),
        "remaining_limit_formatted": format_tl(progress.remaining_limit),
        "remaining_amount": _decimal_text(progress.remaining_amount),
        "remaining_amount_formatted": format_tl(progress.remaining_amount),
        "progress_percent": f"{progress.progress_percent:.1f}",
        "expected_spending_to_date": _decimal_text(progress.expected_spending_to_date),
        "expected_spending_to_date_formatted": format_tl(progress.expected_spending_to_date),
        "status_label": progress.status_label,
        "start_date": goal.start_date.isoformat(),
        "start_date_formatted": format_tr_date(goal.start_date),
        "end_date": goal.end_date.isoformat(),
        "end_date_formatted": format_tr_date(goal.end_date),
        "tactics": progress.tactics,
    }


def _envelope_to_tool_result(envelope: BudgetEnvelope) -> dict[str, object]:
    used_percent = envelope.used_percent
    return {
        "slug": envelope.slug,
        "label": envelope.label,
        "category_name": envelope.category_name,
        "budget": _decimal_text(envelope.budget),
        "budget_formatted": format_tl(envelope.budget),
        "spent": _decimal_text(envelope.spent),
        "spent_formatted": format_tl(envelope.spent),
        "remaining": _decimal_text(envelope.remaining),
        "remaining_formatted": format_tl(envelope.remaining),
        "days_left_in_month": envelope.days_left_in_month,
        "safe_daily_amount": _decimal_text(envelope.safe_daily_amount),
        "safe_daily_amount_formatted": format_tl(envelope.safe_daily_amount),
        "used_percent": f"{used_percent:.1f}" if used_percent is not None else None,
        "status": envelope.status,
        "is_savings_goal": envelope.is_savings_goal,
        "is_custom": envelope.is_custom,
    }


def build_envelope_budget_overview(
    db: Session,
    current_user: User,
    *,
    slug: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    categories = visible_categories(db, current_user)
    period_end = _aware_utc(now or datetime.now(UTC))
    current_month_start = _local_month_start_utc(period_end)
    category_totals: dict[UUID | None, Decimal] = {}
    transactions = list(
        db.execute(
            select(Transaction).where(
                Transaction.user_id.in_(visible_user_ids(current_user)),
                Transaction.occurred_at >= current_month_start,
                Transaction.type == "expense",
            ),
        )
        .scalars()
        .all(),
    )
    for transaction in transactions:
        category_totals[transaction.category_id] = category_totals.get(
            transaction.category_id,
            Decimal("0"),
        ) + Decimal(transaction.amount)
    summary = build_envelope_budget_summary(
        categories=categories,
        current_category_totals=category_totals,
        now=period_end,
    )
    envelopes = [_envelope_to_tool_result(envelope) for envelope in summary.envelopes]
    if slug is not None:
        definition = envelope_definition_for_slug(slug)
        custom_category_id = custom_envelope_category_id(slug)
        if definition is None and custom_category_id is None:
            return {"error": "Zarf bulunamadı.", "slug": slug}
        expected_slug = definition.slug if definition is not None else slug
        envelopes = [item for item in envelopes if item["slug"] == expected_slug]
    return {
        "count": len(envelopes),
        "budgeted_month": _decimal_text(summary.budgeted_month),
        "budgeted_month_formatted": format_tl(summary.budgeted_month),
        "spent_month": _decimal_text(summary.spent_month),
        "spent_month_formatted": format_tl(summary.spent_month),
        "remaining_budget": _decimal_text(summary.remaining_budget),
        "remaining_budget_formatted": format_tl(summary.remaining_budget),
        "envelopes": envelopes,
    }


def build_envelope_budget_update(
    db: Session,
    current_user: User,
    *,
    slug: str,
    budget_monthly: Decimal,
    now: datetime | None = None,
) -> dict[str, object]:
    definition = envelope_definition_for_slug(slug)
    custom_category_id = custom_envelope_category_id(slug)
    if definition is None and custom_category_id is None:
        return {"error": "Zarf bulunamadı.", "slug": slug}
    resolved_slug = definition.slug if definition is not None else slug
    category = set_envelope_budget(
        slug=resolved_slug,
        budget_monthly=_money(budget_monthly),
        db=db,
        current_user=current_user,
    )
    overview = build_envelope_budget_overview(db, current_user, slug=resolved_slug, now=now)
    envelopes = overview.get("envelopes")
    envelope = envelopes[0] if isinstance(envelopes, list) and envelopes else None
    return {
        "updated": True,
        "slug": resolved_slug,
        "category_id": str(category.id),
        "category_name": category.name,
        "budget_monthly": _decimal_text(_money(budget_monthly)),
        "budget_monthly_formatted": format_tl(_money(budget_monthly)),
        "envelope": envelope,
    }


def build_envelope_budget_creation(
    db: Session,
    current_user: User,
    *,
    name: str,
    budget_monthly: Decimal,
    now: datetime | None = None,
) -> dict[str, object]:
    normalized_name = " ".join(name.split())
    if len(normalized_name) < 2:
        return {"error": "Zarf adı boş olamaz.", "name": name}
    category = create_envelope_category(
        name=normalized_name,
        budget_monthly=_money(budget_monthly),
        db=db,
        current_user=current_user,
    )
    overview = build_envelope_budget_overview(db, current_user, now=now)
    envelopes = overview.get("envelopes")
    envelope = None
    if isinstance(envelopes, list):
        envelope = next(
            (
                item
                for item in envelopes
                if isinstance(item, dict)
                and str(item.get("category_name", "")).casefold() == category.name.casefold()
            ),
            None,
        )
    slug = str(envelope.get("slug")) if isinstance(envelope, dict) else f"custom-{category.id}"
    return {
        "created": True,
        "slug": slug,
        "category_id": str(category.id),
        "category_name": category.name,
        "budget_monthly": _decimal_text(_money(budget_monthly)),
        "budget_monthly_formatted": format_tl(_money(budget_monthly)),
        "envelope": envelope,
    }


def build_envelope_budget_delete(
    db: Session,
    current_user: User,
    *,
    slug: str,
    now: datetime | None = None,
) -> dict[str, object]:
    result = build_envelope_budget_update(
        db,
        current_user,
        slug=slug,
        budget_monthly=Decimal("0.00"),
        now=now,
    )
    if "error" in result:
        return result
    return {**result, "deleted": True, "disabled": True}


def build_saving_goal_creation(
    db: Session,
    current_user: User,
    *,
    category: str,
    target_reduction_percent: object = 15,
    now: datetime | None = None,
) -> dict[str, object]:
    category_name = resolve_envelope_category(category) or category
    try:
        reduction = parse_int_text(
            target_reduction_percent,
            default=15,
            min_value=1,
            max_value=50,
        )
        goal = create_saving_goal(
            db,
            current_user,
            category_name=category_name,
            target_reduction_percent=Decimal(reduction),
            created_by="agent",
            now=now,
        )
    except ValueError as exc:
        return {"error": str(exc), "category": category_name}
    progress = calculate_saving_goal_progress(db, goal, now=now)
    return {"created": True, **_progress_to_tool_result(progress)}


def build_accumulation_goal_creation(
    db: Session,
    current_user: User,
    *,
    title: str,
    target_amount: Decimal,
    current_amount: Decimal = Decimal("0"),
    target_months: object = 12,
    monthly_contribution: Decimal | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    period_start = _aware_utc(now or datetime.now(UTC))
    safe_months = parse_int_text(target_months, default=12, min_value=1, max_value=120)
    target_date = _add_months(_month_start(period_start), safe_months)
    target_end = datetime(target_date.year, target_date.month, target_date.day, tzinfo=UTC)
    try:
        goal = create_accumulation_goal(
            db,
            current_user,
            target_amount=target_amount,
            current_amount=current_amount,
            monthly_contribution=monthly_contribution,
            target_date=target_end,
            title=title,
            created_by="agent",
            now=period_start,
        )
    except ValueError as exc:
        return {"error": str(exc), "title": title}
    progress = calculate_saving_goal_progress(db, goal, now=period_start)
    return {"created": True, **_progress_to_tool_result(progress)}


def build_saving_goal_progress(
    db: Session,
    current_user: User,
    *,
    category: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    category_name = resolve_envelope_category(category) if category else None
    if category_name is None:
        category_name = category
    goal = find_active_saving_goal(db, current_user, category_name=category_name)
    if goal is None:
        return {
            "error": "Bu kategori için aktif tasarruf hedefi bulamadım.",
            "category": category_name,
        }
    return _progress_to_tool_result(calculate_saving_goal_progress(db, goal, now=now))


def build_saving_goals_overview(
    db: Session,
    current_user: User,
    *,
    status: str = "active",
    now: datetime | None = None,
) -> dict[str, object]:
    query = select(SavingGoal).where(SavingGoal.user_id.in_(visible_user_ids(current_user)))
    if status != "all":
        query = query.where(SavingGoal.status == status)
    goals = list(db.execute(query.order_by(SavingGoal.created_at.desc())).scalars().all())
    rows = [
        _progress_to_tool_result(calculate_saving_goal_progress(db, goal, now=now))
        for goal in goals
    ]
    return {
        "count": len(rows),
        "status": status,
        "goals": rows,
    }


def _find_scoped_goal(
    db: Session,
    current_user: User,
    *,
    goal_id: str | None = None,
    title: str | None = None,
    category: str | None = None,
) -> SavingGoal | None:
    query = select(SavingGoal).where(SavingGoal.user_id.in_(visible_user_ids(current_user)))
    if goal_id is not None:
        try:
            parsed_goal_id = UUID(goal_id)
        except ValueError:
            return None
        query = query.where(SavingGoal.id == parsed_goal_id)
        return db.execute(query).scalar_one_or_none()

    goals = list(db.execute(query.order_by(SavingGoal.created_at.desc())).scalars().all())
    if title is not None:
        normalized_title = _normalized_text(title)
        matched = next(
            (
                goal
                for goal in goals
                if normalized_title
                and (
                    normalized_title in _normalized_text(goal.title)
                    or _normalized_text(goal.title) in normalized_title
                )
            ),
            None,
        )
        if matched is not None:
            return matched

    if category is not None:
        category_name = resolve_envelope_category(category) or category
        active_goal = find_active_saving_goal(db, current_user, category_name=category_name)
        if active_goal is not None:
            return active_goal

    return goals[0] if len(goals) == 1 else None


def build_saving_goal_update(
    db: Session,
    current_user: User,
    *,
    goal_id: str | None = None,
    title: str | None = None,
    category: str | None = None,
    new_title: str | None = None,
    status: str | None = None,
    current_amount: Decimal | None = None,
    contribution_amount: Decimal | None = None,
    monthly_contribution: Decimal | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    goal = _find_scoped_goal(db, current_user, goal_id=goal_id, title=title, category=category)
    if goal is None:
        return {"error": "Hedef bulunamadı.", "goal_id": goal_id, "title": title}
    goal_status: SavingGoalStatus | None = None
    if status is not None:
        if status == "active":
            goal_status = "active"
        elif status == "completed":
            goal_status = "completed"
        elif status == "paused":
            goal_status = "paused"
        else:
            return {"error": "Hedef durumu active, paused veya completed olmalı."}

    try:
        updated = update_saving_goal(
            db,
            goal,
            SavingGoalUpdate(
                title=new_title,
                status=goal_status,
                current_amount=current_amount,
                contribution_amount=contribution_amount,
                monthly_contribution=monthly_contribution,
            ),
        )
    except ValueError as exc:
        return {"error": str(exc), "goal_id": str(goal.id)}
    progress = calculate_saving_goal_progress(db, updated, now=now)
    return {"updated": True, **_progress_to_tool_result(progress)}


def build_saving_goal_delete(
    db: Session,
    current_user: User,
    *,
    goal_id: str | None = None,
    title: str | None = None,
    category: str | None = None,
) -> dict[str, object]:
    goal = _find_scoped_goal(db, current_user, goal_id=goal_id, title=title, category=category)
    if goal is None:
        return {"error": "Hedef bulunamadı.", "goal_id": goal_id, "title": title}
    result = {
        "deleted": True,
        "goal_id": str(goal.id),
        "goal_type": goal.goal_type,
        "title": goal.title,
    }
    db.delete(goal)
    db.commit()
    return result


def build_saving_goal_delete_by_id(
    db: Session,
    current_user: User,
    goal_id: UUID,
) -> dict[str, object]:
    return build_saving_goal_delete(db, current_user, goal_id=str(goal_id))


def build_saving_goals_chart(
    db: Session,
    current_user: User,
    *,
    status: str = "active",
    now: datetime | None = None,
) -> dict[str, object]:
    overview = build_saving_goals_overview(db, current_user, status=status, now=now)
    goals = overview.get("goals")
    data: list[dict[str, object]] = []
    if isinstance(goals, list):
        for item in goals:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "Hedef")
            progress = Decimal(str(item.get("progress_percent") or "0"))
            chart_progress = min(max(progress, Decimal("0")), Decimal("100"))
            data.append(
                {
                    "label": title[:28],
                    "value": f"{chart_progress:.1f}",
                    "value_formatted": f"%{chart_progress:.1f}",
                },
            )
    return {
        **overview,
        "chart": {
            "type": "bar",
            "title": "Aktif hedefler",
            "subtitle": "Birikim ve tasarruf ilerlemesi",
            "data": data,
            "value_label": "İlerleme",
            "currency": None,
        },
    }


def build_subscriptions_summary(
    db: Session,
    current_user: User,
    *,
    only_active: bool = True,
) -> dict[str, object]:
    """Return scoped subscriptions and their MVP monthly equivalent total."""
    query = select(Subscription).where(Subscription.user_id.in_(visible_user_ids(current_user)))
    if only_active:
        query = query.where(Subscription.is_active.is_(True))

    subscriptions = list(
        db.execute(query.order_by(Subscription.next_billing_date, Subscription.name))
        .scalars()
        .all(),
    )

    rows: list[dict[str, object]] = []
    monthly_total = Decimal("0")
    for subscription in subscriptions:
        monthly = monthly_equivalent(
            Decimal(subscription.amount),
            subscription.recurrence_interval,
            subscription.recurrence_unit,
            subscription.billing_cycle,
        )
        monthly_total += monthly
        rows.append(
            {
                "id": str(subscription.id),
                "name": subscription.name,
                "merchant": subscription.merchant,
                "amount": _decimal_text(Decimal(subscription.amount)),
                "amount_formatted": format_tl(Decimal(subscription.amount)),
                "billing_cycle": subscription.billing_cycle,
                "recurrence_interval": subscription.recurrence_interval,
                "recurrence_unit": subscription.recurrence_unit,
                "recurrence_label": recurrence_label(
                    subscription.recurrence_interval,
                    subscription.recurrence_unit,
                    subscription.billing_cycle,
                ),
                "next_billing_date": (
                    subscription.next_billing_date.isoformat()
                    if subscription.next_billing_date
                    else None
                ),
                "next_billing_date_formatted": (
                    format_tr_date(subscription.next_billing_date)
                    if subscription.next_billing_date
                    else None
                ),
                "is_active": subscription.is_active,
                "usage_score": (
                    _decimal_text(Decimal(subscription.usage_score))
                    if subscription.usage_score is not None
                    else None
                ),
                "monthly_equivalent": _decimal_text(monthly),
                "monthly_equivalent_formatted": format_tl(monthly),
            },
        )

    return {
        "only_active": only_active,
        "count": len(rows),
        "monthly_total": _decimal_text(monthly_total),
        "monthly_total_formatted": format_tl(monthly_total),
        "subscriptions": rows,
    }


def build_user_memory(
    db: Session,
    current_user: User,
    *,
    key: str | None = None,
) -> dict[str, object]:
    """Return memory entries for the current user only."""
    query = select(AgentMemory).where(AgentMemory.user_id == current_user.id)
    if key is not None:
        query = query.where(AgentMemory.key == key)

    memories = list(db.execute(query.order_by(AgentMemory.key)).scalars().all())
    return {
        "key": key,
        "count": len(memories),
        "entries": [{"key": memory.key, "value": memory.value} for memory in memories],
    }


def build_memory_upsert(
    db: Session,
    current_user: User,
    *,
    text: str,
    key: str | None = None,
    source: str = "chat",
) -> dict[str, object]:
    """Store an explicit, safe memory entry for the active profile only."""
    clean_text = " ".join(text.strip().split())
    if not clean_text:
        return {"saved": False, "error": "Hatırlanacak bilgi boş olamaz."}
    if not _memory_text_is_safe(clean_text):
        return {
            "saved": False,
            "blocked": True,
            "error": "Bu bilgi hassas görünüyor; güvenlik için hafızaya kaydetmedim.",
        }

    memory_key = key or _memory_key_from_text(clean_text)
    existing = db.execute(
        select(AgentMemory).where(
            AgentMemory.user_id == current_user.id,
            AgentMemory.key == memory_key,
        ),
    ).scalar_one_or_none()
    value: dict[str, object] = {"text": clean_text, "source": source}
    created = existing is None
    if existing is None:
        existing = AgentMemory(user_id=current_user.id, key=memory_key, value=value)
        db.add(existing)
    else:
        existing.value = value
    db.commit()
    db.refresh(existing)
    return {
        "saved": True,
        "created": created,
        "key": existing.key,
        "value": existing.value,
    }


def build_receipt_candidate(
    db: Session,
    current_user: User,
    *,
    image_base64: str,
    filename: str = "receipt.jpg",
    content_type: str = "image/jpeg",
) -> dict[str, object]:
    """Analyze a receipt image from trusted agent state scope."""
    try:
        content = base64.b64decode(image_base64, validate=True)
    except binascii.Error:
        return {"error": "Fiş görseli çözümlenemedi."}
    if len(content) > 5 * 1024 * 1024:
        return {"error": "Fiş dosyası en fazla 5 MB olmalı."}
    try:
        candidate = ReceiptOcrService().analyze(
            content=content,
            content_type=content_type,
            filename=filename,
            receipt_image_url="agent://receipt-preview",
            categories=visible_categories(db, current_user),
        )
    except ReceiptOcrUnavailableError:
        return {"error": "OCR servisi hazır değil."}
    except ReceiptOcrError:
        return {"error": "Fiş okunamadı."}
    result = candidate.model_dump(mode="json")
    raw_ocr_data = result.get("raw_ocr_data")
    if isinstance(raw_ocr_data, dict):
        result["raw_ocr_data"] = {
            "provider": raw_ocr_data.get("provider"),
            "source_filename": raw_ocr_data.get("source_filename"),
        }
    return result


def _unique_labels(labels: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(label for label in labels if label))


def _chart_target_values(
    *,
    category: str | None,
    target: str | None,
    targets: list[str] | None,
) -> list[str]:
    values: list[str] = []
    if category:
        values.append(category)
    if target:
        values.append(target)
    if targets:
        values.extend(targets)
    return [value for value in values if value.strip()]


def _category_label(transaction: Transaction, category_names: dict[UUID, str]) -> str:
    if transaction.category_id is None:
        return "Kategorisiz"
    return category_names.get(transaction.category_id, "Kategorisiz")


def _select_category_labels(
    categories: list[Category],
    *,
    target_values: list[str],
    query: str | None,
) -> list[str]:
    labels = [category.name for category in categories]
    if target_values:
        return _unique_labels(label for label in labels if _matches_text(label, target_values))
    if query:
        return _unique_labels(label for label in labels if _matches_text(label, [query]))
    return []


def _subscription_texts(subscription: Subscription) -> list[str]:
    return [subscription.name, subscription.merchant or ""]


def _select_subscriptions(
    subscriptions: list[Subscription],
    *,
    target_values: list[str],
    query: str | None,
) -> list[Subscription]:
    if target_values:
        return [
            subscription
            for subscription in subscriptions
            if any(_matches_text(text, target_values) for text in _subscription_texts(subscription))
        ]
    if query:
        return [
            subscription
            for subscription in subscriptions
            if any(_matches_text(text, [query]) for text in _subscription_texts(subscription))
        ]
    return []


def _transaction_subscription_id(transaction: Transaction) -> str | None:
    raw_data = transaction.raw_ocr_data
    if not isinstance(raw_data, dict):
        return None
    value = raw_data.get("subscription_id")
    return str(value) if value is not None else None


def _transaction_texts(transaction: Transaction) -> list[str]:
    return [transaction.merchant or "", transaction.description or ""]


def _matches_subscription(transaction: Transaction, subscription: Subscription) -> bool:
    if _transaction_subscription_id(transaction) == str(subscription.id):
        return True
    transaction_texts = _transaction_texts(transaction)
    return any(
        _matches_text(text, transaction_texts) for text in _subscription_texts(subscription) if text
    )


def _select_merchant_labels(
    transactions: list[Transaction],
    *,
    target_values: list[str],
    query: str | None,
) -> list[str]:
    labels = _unique_labels(transaction.merchant or "" for transaction in transactions)
    if target_values:
        return _unique_labels(label for label in labels if _matches_text(label, target_values))
    if query:
        return _unique_labels(label for label in labels if _matches_text(label, [query]))
    return []


def _infer_monthly_target_type(
    *,
    target_type: str | None,
    query: str | None,
    target_values: list[str],
    category_labels: list[str],
    subscriptions: list[Subscription],
    merchant_labels: list[str],
) -> str:
    requested = _normalized_text(target_type)
    if requested in {
        "subscription",
        "subscriptions",
        "abonelik",
        "merchant",
        "vendor",
        "satıcı",
        "satici",
    }:
        return "subscription"
    if requested in {"category", "kategori"}:
        return "category"
    haystack = " ".join([query or "", *target_values])
    if any(
        hint in _normalized_text(haystack)
        for hint in ("abonelik", "tekrarlayan", "satıcı", "satici")
    ):
        return "subscription"
    if any(_matches_text(label, [haystack]) for label in category_labels):
        return "category"
    if any(
        any(_matches_text(text, [haystack]) for text in _subscription_texts(item))
        for item in subscriptions
    ):
        return "subscription"
    if any(_matches_text(label, [haystack]) for label in merchant_labels):
        return "subscription"
    return "category"


def _top_series_labels(series_totals: dict[str, Decimal]) -> list[str]:
    return [
        label
        for label, total in sorted(series_totals.items(), key=lambda item: item[1], reverse=True)
        if total > 0
    ][:MONTHLY_TREND_MAX_SERIES]


def _build_monthly_points(
    *,
    months: list[date],
    series_labels: list[str],
    monthly_totals: dict[date, dict[str, Decimal]],
) -> list[dict[str, object]]:
    return [
        {
            "label": _month_label(month),
            "series": label,
            "value": _decimal_text(monthly_totals.get(month, {}).get(label, Decimal("0"))),
            "value_formatted": format_tl(monthly_totals.get(month, {}).get(label, Decimal("0"))),
        }
        for month in months
        for label in series_labels
    ]


def _build_monthly_spending_chart(
    db: Session,
    current_user: User,
    *,
    days: int,
    category: str | None,
    target: str | None,
    targets: list[str] | None,
    target_type: str | None,
    query: str | None,
    now: datetime | None,
) -> dict[str, object]:
    safe_days = max(_normalized_days(days), MONTHLY_TREND_MIN_DAYS)
    period_end = _aware_utc(now or datetime.now(UTC))
    period_start = period_end - timedelta(days=safe_days)
    months = _month_range(period_start, period_end)
    user_ids = visible_user_ids(current_user)
    categories = visible_categories(db, current_user)
    category_names = {item.id: item.name for item in categories}
    target_values = _chart_target_values(category=category, target=target, targets=targets)

    transactions = list(
        db.execute(
            select(Transaction)
            .where(
                Transaction.user_id.in_(user_ids),
                Transaction.occurred_at >= period_start,
                Transaction.type == "expense",
            )
            .order_by(Transaction.occurred_at.asc()),
        )
        .scalars()
        .all(),
    )
    transactions = [item for item in transactions if _aware_utc(item.occurred_at) <= period_end]
    subscriptions = list(
        db.execute(
            select(Subscription)
            .where(Subscription.user_id.in_(user_ids))
            .order_by(Subscription.name),
        )
        .scalars()
        .all(),
    )
    mode = _infer_monthly_target_type(
        target_type=target_type,
        query=query,
        target_values=target_values,
        category_labels=[item.name for item in categories],
        subscriptions=subscriptions,
        merchant_labels=_unique_labels(item.merchant or "" for item in transactions),
    )
    monthly_totals: dict[date, dict[str, Decimal]] = {}
    series_totals: dict[str, Decimal] = {}
    selected_series: list[str] = []
    transaction_count = 0

    def add_total(transaction: Transaction, label: str) -> None:
        nonlocal transaction_count
        amount = Decimal(transaction.amount)
        month = _month_start(transaction.occurred_at)
        monthly_totals.setdefault(month, {})[label] = (
            monthly_totals.setdefault(month, {}).get(label, Decimal("0")) + amount
        )
        series_totals[label] = series_totals.get(label, Decimal("0")) + amount
        transaction_count += 1

    if mode == "subscription":
        selected_subscriptions = _select_subscriptions(
            subscriptions,
            target_values=target_values,
            query=query,
        )
        selected_merchants = _select_merchant_labels(
            transactions,
            target_values=target_values,
            query=query,
        )
        subscription_pool = selected_subscriptions or subscriptions
        selected_series = _unique_labels(item.name for item in selected_subscriptions)
        selected_series.extend(
            label for label in selected_merchants if label not in selected_series
        )
        for transaction in transactions:
            label = next(
                (
                    subscription.name
                    for subscription in subscription_pool
                    if _matches_subscription(transaction, subscription)
                ),
                None,
            )
            if label is None and selected_merchants:
                merchant = transaction.merchant or ""
                label = merchant if merchant in selected_merchants else None
            if label is None and not selected_series and transaction.source == "recurring":
                label = transaction.merchant or transaction.description or "Tekrarlayan ödeme"
            if label is not None:
                add_total(transaction, label)
        if not selected_series:
            selected_series = _top_series_labels(series_totals)
    else:
        selected_series = _select_category_labels(
            categories,
            target_values=target_values,
            query=query,
        )
        selected_set = set(selected_series)
        for transaction in transactions:
            label = _category_label(transaction, category_names)
            if selected_set and label not in selected_set:
                continue
            if target_values and not selected_set:
                continue
            add_total(transaction, label)
        if not selected_series:
            selected_series = _top_series_labels(series_totals)

    selected_series = selected_series[:MONTHLY_TREND_MAX_SERIES]
    total_amount = sum(
        (series_totals.get(label, Decimal("0")) for label in selected_series), Decimal("0")
    )
    title_target = selected_series[0] if len(selected_series) == 1 else None
    title = f"{title_target} aylık harcama trendi" if title_target else "Aylık harcama trendi"
    subtitle = (
        f"{_month_label(months[0])} - {_month_label(months[-1])}, toplam {format_tl(total_amount)}"
    )

    return {
        "days": safe_days,
        "month_count": len(months),
        "target_type": mode,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "transaction_count": transaction_count,
        "total_amount_formatted": format_tl(total_amount),
        "chart": {
            "type": "monthly",
            "title": title,
            "subtitle": subtitle,
            "data": _build_monthly_points(
                months=months,
                series_labels=selected_series,
                monthly_totals=monthly_totals,
            ),
            "value_label": "Tutar",
            "currency": "TRY",
        },
    }


def build_spending_chart(
    db: Session,
    current_user: User,
    *,
    days: int = 30,
    chart_type: str = "bar",
    category: str | None = None,
    target: str | None = None,
    targets: list[str] | None = None,
    target_type: str | None = None,
    query: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return a chart specification of the user's category spending.

    The chart payload is rendered inline by the frontend when it sees a `chart`
    key on a tool_result event. Same `visible_user_ids` scope as get_spending.
    """
    if chart_type not in {"bar", "pie", "monthly"}:
        chart_type = "bar"
    if chart_type == "monthly":
        return _build_monthly_spending_chart(
            db,
            current_user,
            days=days,
            category=category,
            target=target,
            targets=targets,
            target_type=target_type,
            query=query,
            now=now,
        )

    summary = build_spending_summary(db, current_user, category=category, days=days, now=now)
    rows = summary.get("category_totals")
    if not isinstance(rows, list):
        rows = []

    points = [
        {
            "label": str(row.get("category", "Kategorisiz")),
            "value": _decimal_text(Decimal(str(row.get("amount", "0")))),
            "value_formatted": str(row.get("amount_formatted", "0,00 ₺")),
        }
        for row in rows
    ]
    total = summary.get("total_amount_formatted", "0,00 ₺")
    days_value = summary.get("days", days)
    title = f"Son {days_value} gün kategori bazında harcama"
    subtitle = f"Toplam {total}"

    return {
        "days": days_value,
        "period_start": summary.get("period_start"),
        "period_end": summary.get("period_end"),
        "transaction_count": summary.get("transaction_count", 0),
        "total_amount_formatted": total,
        "chart": {
            "type": chart_type,
            "title": title,
            "subtitle": subtitle,
            "data": points,
            "value_label": "Tutar",
            "currency": "TRY",
        },
    }


def _illustration_forbidden(concept: str) -> bool:
    normalized = concept.casefold()
    return any(term in normalized for term in BLOCKED_ILLUSTRATION_TERMS)


def _illustration_day_start_utc(now: datetime | None = None) -> datetime:
    local_now = _aware_utc(now or datetime.now(UTC)).astimezone(ISTANBUL_TZ)
    return local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def _daily_illustration_count(db: Session, current_user: User) -> int:
    day_start = _illustration_day_start_utc()
    count = db.execute(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == current_user.id,
            Message.tool_name == "illustrate_concept",
            Message.created_at >= day_start,
        ),
    ).scalar_one()
    return int(count)


def build_concept_illustration(
    db: Session,
    current_user: User,
    *,
    concept: str,
) -> dict[str, object]:
    """Generate a safe educational concept illustration for the current user."""
    normalized = " ".join(concept.split()) or "finansal kavram"
    if _illustration_forbidden(normalized):
        return {
            "concept": normalized,
            "error": "Görsel anlatımı yalnızca eğitim amaçlı finans kavramları için kullanabilirim.",
        }

    settings = get_settings()
    provider_key_available = (
        bool(settings.openrouter_api_key)
        if settings.llm_provider == "openrouter"
        else bool(settings.gemini_api_key)
    )
    if not provider_key_available:
        return {
            "concept": normalized,
            "error": "Görsel anlatım servisi şu an hazır değil.",
        }

    daily_limit = max(1, settings.illustration_daily_limit)
    if _daily_illustration_count(db, current_user) >= daily_limit:
        return {
            "concept": normalized,
            "daily_limit": daily_limit,
            "error": f"Bugünkü {daily_limit} görsel sınırına ulaştın.",
        }

    audience = (
        "child"
        if current_user.role == "child" or current_user.finance_level == "child"
        else "adult"
    )
    try:
        illustration = IllustrationService(settings).illustrate(
            user_id=current_user.id,
            concept=normalized,
            audience=audience,
        )
    except IllustrationUnavailableError as exc:
        return {"concept": normalized, "error": str(exc)}

    return {
        "concept": normalized,
        "image_url": illustration.public_url,
        "alt_text": f"{normalized} kavramını anlatan eğitim amaçlı illüstrasyon",
    }


def explain_finance_concept(current_user: User, *, concept: str) -> dict[str, object]:
    normalized = " ".join(concept.split()) or "finansal kavram"
    is_child = current_user.role == "child" or current_user.finance_level == "child"
    if "faiz" in normalized.casefold():
        explanation = (
            "Faiz, paranı bir süre beklettiğinde bankanın sana eklediği küçük teşekkür parası gibi "
            "düşünülebilir. Diyelim kumbaranda 100 ₺ var ve banka ay sonunda 2 ₺ ekledi; artık "
            "102 ₺ olur. Borçta ise durum tersine döner: banka sana para verdiğinde geri alırken "
            "fazladan para ister."
            if is_child
            else "Faiz, paranın zaman değeridir. Birikimde paran beklediği için ek getiri sağlar; "
            "borçta ise kullandığın para için ek maliyet oluşturur."
        )
    elif "enflasyon" in normalized.casefold():
        explanation = (
            "Enflasyon, aynı harçlıkla zamanla daha az şey alabilmendir. Bugün 50 ₺ ile iki dondurma "
            "alırken birkaç ay sonra aynı para bir buçuk dondurmaya yetebilir."
            if is_child
            else "Enflasyon, fiyatların genel seviyesinin artmasıdır; aynı bütçeyle daha az ürün veya "
            "hizmet alınmasına yol açar."
        )
    else:
        explanation = (
            f"{normalized} konusunu basitçe paranın nasıl kazanıldığı, saklandığı ve harcandığıyla "
            "ilgili bir kural gibi düşünebilirsin."
            if is_child
            else f"{normalized} için temel yaklaşım, nakit akışına etkisini ve toplam maliyeti ayrı "
            "ayrı değerlendirmektir."
        )
    return {"concept": normalized, "level": current_user.finance_level, "explanation": explanation}


def _normalize_lesson_level(level: str, current_user: User) -> str:
    normalized = level.casefold().strip()
    tr_map = {
        "çocuk": "child",
        "cocuk": "child",
        "başlangıç": "beginner",
        "baslangic": "beginner",
        "orta": "intermediate",
        "ileri": "advanced",
    }
    normalized = tr_map.get(normalized, normalized)
    if normalized in CUSTOM_LESSON_LEVELS:
        return normalized
    if current_user.finance_level in CUSTOM_LESSON_LEVELS:
        return current_user.finance_level
    return "beginner"


def _lesson_level_label(level: str) -> str:
    return {
        "child": "Çocuk",
        "beginner": "Başlangıç",
        "intermediate": "Orta",
        "advanced": "İleri",
    }.get(level, "Başlangıç")


def _custom_lesson_forbidden(topic: str) -> bool:
    normalized = topic.casefold()
    return any(re.search(pattern, normalized) for pattern in CUSTOM_LESSON_BLOCKED_ADVICE_PATTERNS)


def _custom_lesson_goals(topic: str, level: str) -> list[str]:
    if level == "child":
        return [
            f"{topic} konusunu günlük hayattan bir örnekle tanımak.",
            "Harçlık, kumbara veya okul alışverişi üzerinden küçük bir karar vermek.",
            "Ders sonunda kendi cümlesiyle bir güvenli para alışkanlığı söylemek.",
        ]
    return [
        f"{topic} kavramının aile bütçesine etkisini anlamak.",
        "Gelir, gider, risk ve zaman etkisini birbirinden ayırmak.",
        "Kendi bütçesinde uygulanabilir küçük bir takip adımı seçmek.",
    ]


def _custom_lesson_sections(
    topic: str, level: str, duration_minutes: int
) -> list[dict[str, object]]:
    intro_minutes = 1
    practice_minutes = max(1, duration_minutes - 3)
    wrap_minutes = max(1, duration_minutes - intro_minutes - practice_minutes)
    if level == "child":
        return [
            {
                "title": "Kısa hikaye",
                "minutes": intro_minutes,
                "content": f"{topic} konusunu harçlık ve kumbara üzerinden tek cümleyle tanıt.",
            },
            {
                "title": "Birlikte düşün",
                "minutes": practice_minutes,
                "content": "Bir oyuncak, kantin veya doğum günü hediyesi seçimiyle küçük karar oyunu yap.",
            },
            {
                "title": "Mini söz",
                "minutes": wrap_minutes,
                "content": "Çocuğun bugün deneyebileceği tek para alışkanlığını seçtir.",
            },
        ]
    return [
        {
            "title": "Temel kavram",
            "minutes": intro_minutes,
            "content": f"{topic} nedir, aile bütçesinde hangi satıra dokunur?",
        },
        {
            "title": "Bütçe üzerinde oku",
            "minutes": practice_minutes,
            "content": "Gelir, gider, tekrar eden ödeme veya hedef zarfı üzerinden somut bir örnek kur.",
        },
        {
            "title": "Uygulanabilir adım",
            "minutes": wrap_minutes,
            "content": "Bugün yapılabilecek tek takip veya karşılaştırma adımını yaz.",
        },
    ]


def _custom_lesson_examples(topic: str, level: str) -> list[str]:
    if level == "child":
        return [
            f"Kumbaranda 100 ₺ varsa {topic} kararını nasıl etkiler?",
            "Kantin alışverişinden önce ihtiyaç ve istek ayrımı yap.",
        ]
    return [
        f"Aylık bütçede {topic} için küçük bir kontrol satırı aç.",
        "Tekrarlayan bir ödemeyi veya hedef katkısını ay sonunda gerçekleşen tutarla karşılaştır.",
    ]


def _custom_lesson_quiz(topic: str, level: str) -> list[dict[str, object]]:
    if level == "child":
        return [
            {
                "question": f"{topic} kararında ilk neye bakarsın?",
                "answer": "Gerçekten gerekli mi ve kumbaramdaki hedefi etkiler mi diye bakarım.",
            },
            {
                "question": "Küçük birikim neden işe yarar?",
                "answer": "Çünkü küçük tutarlar zamanla büyür ve hedefe yaklaşmayı gösterir.",
            },
        ]
    return [
        {
            "question": f"{topic} bütçede hangi soruyla kontrol edilir?",
            "answer": "Gelirimi, giderimi, riskimi veya hedef süremi nasıl etkiliyor?",
        },
        {
            "question": "Bu ders yatırım tavsiyesi verir mi?",
            "answer": "Hayır; sadece finansal okuryazarlık ve bütçe alışkanlığı anlatır.",
        },
    ]


def build_custom_lesson(
    current_user: User,
    *,
    topic: str,
    level: str = "beginner",
    duration_minutes: int = 5,
    include_examples: bool = True,
    include_quiz: bool = True,
    visual: bool = False,
) -> dict[str, object]:
    """Return a transient Finance School lesson plan without persisting it."""
    normalized_topic = " ".join(topic.split())
    if not normalized_topic:
        return {"error": "Ders konusu boş olamaz."}
    if _custom_lesson_forbidden(normalized_topic):
        return {
            "topic": normalized_topic,
            "error": "Özel ders oluşturabilirim ama belirli ürün, al-sat veya getiri tavsiyesi veremem.",
        }
    safe_duration = max(3, min(duration_minutes, 12))
    safe_level = _normalize_lesson_level(level, current_user)
    lesson: dict[str, object] = {
        "title": f"{normalized_topic}: {_lesson_level_label(safe_level)} dersi",
        "topic": normalized_topic,
        "level": safe_level,
        "level_label": _lesson_level_label(safe_level),
        "duration_minutes": safe_duration,
        "learning_goals": _custom_lesson_goals(normalized_topic, safe_level),
        "sections": _custom_lesson_sections(normalized_topic, safe_level, safe_duration),
        "examples": _custom_lesson_examples(normalized_topic, safe_level)
        if include_examples
        else [],
        "mini_quiz": _custom_lesson_quiz(normalized_topic, safe_level) if include_quiz else [],
        "safety_note": "Bu ders eğitim amaçlıdır; belirli ürün, getiri, al/sat/tut tavsiyesi vermez.",
        "visual": visual,
        "illustration_prompt": normalized_topic if visual else None,
    }
    return lesson


def simulate_finance_scenario(
    db: Session,
    current_user: User,
    *,
    scenario: str,
) -> dict[str, object]:
    normalized = scenario.casefold()
    if "asgari" in normalized or "kredi kart" in normalized:
        user_ids = visible_user_ids(current_user)
        transactions = list(
            db.execute(
                select(Transaction)
                .where(
                    Transaction.user_id.in_(user_ids),
                    Transaction.occurred_at >= datetime.now(UTC) - timedelta(days=30),
                )
                .order_by(Transaction.occurred_at.desc()),
            )
            .scalars()
            .all(),
        )
        expenses = sum(
            (Decimal(item.amount) for item in transactions if item.type == "expense"),
            Decimal("0"),
        )
        monthly_rate = Decimal("0.0366")
        interest = _money(expenses * monthly_rate)
        return {
            "scenario": "credit_card_minimum",
            "current_expense_base": _decimal_text(expenses),
            "current_expense_base_formatted": format_tl(expenses),
            "estimated_monthly_interest": _decimal_text(interest),
            "estimated_monthly_interest_formatted": format_tl(interest),
            "summary": (
                f"Son 30 gün gider bazın {format_tl(expenses)}. Asgari ödeme alışkanlığı bu "
                f"tutar üzerinde yaklaşık {format_tl(interest)} aylık faiz yükü oluşturabilir."
            ),
        }
    return {
        "scenario": "general",
        "summary": "Bu senaryo için net hesap yapmam için tutar, tarih ve ödeme planı gerekir.",
    }


@tool("get_spending")
def get_spending_tool(
    category: str | None = None,
    days: int | str = 30,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Kullanıcının harcama özetini döner. `user_id` sistem durumundan gelir."""
    with SessionLocal() as db:
        return build_spending_summary(
            db,
            _load_current_user(db, user_id),
            category=category,
            days=parse_int_text(days, default=30, min_value=1, max_value=MAX_SPENDING_DAYS),
        )


@tool("get_subscriptions")
def get_subscriptions_tool(
    only_active: bool | str = True,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Kullanıcının abonelik ve tekrarlayan ödeme özetini döner."""
    with SessionLocal() as db:
        return build_subscriptions_summary(
            db,
            _load_current_user(db, user_id),
            only_active=parse_bool_text(only_active, default=True),
        )


@tool("create_saving_goal")
def create_saving_goal_tool(
    category: str,
    target_reduction_percent: int | str = 15,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Bir gider kategorisinde harcama azaltma hedefi oluşturur."""
    with SessionLocal() as db:
        return build_saving_goal_creation(
            db,
            _load_current_user(db, user_id),
            category=category,
            target_reduction_percent=target_reduction_percent,
        )


@tool("get_saving_goal_progress")
def get_saving_goal_progress_tool(
    category: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Aktif kategori tasarruf hedefinin ilerlemesini döner."""
    with SessionLocal() as db:
        return build_saving_goal_progress(db, _load_current_user(db, user_id), category=category)


@tool("get_saving_goals")
def get_saving_goals_tool(
    status: str = "active",
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Kullanıcının mevcut birikim ve tasarruf hedeflerini listeler."""
    with SessionLocal() as db:
        return build_saving_goals_overview(db, _load_current_user(db, user_id), status=status)


@tool("update_saving_goal")
def update_saving_goal_tool(
    goal_id: str | None = None,
    title: str | None = None,
    category: str | None = None,
    new_title: str | None = None,
    status: str | None = None,
    current_amount: str | None = None,
    contribution_amount: str | None = None,
    monthly_contribution: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Mevcut birikim veya tasarruf hedefini günceller."""
    with SessionLocal() as db:
        try:
            parsed_current = (
                parse_money_text(current_amount) if current_amount is not None else None
            )
            parsed_contribution = (
                parse_money_text(contribution_amount) if contribution_amount is not None else None
            )
            parsed_monthly = (
                parse_money_text(monthly_contribution) if monthly_contribution is not None else None
            )
        except InvalidOperation:
            return {"error": "Tutarları net okuyamadım."}
        return build_saving_goal_update(
            db,
            _load_current_user(db, user_id),
            goal_id=goal_id,
            title=title,
            category=category,
            new_title=new_title,
            status=parse_goal_status_text(status),
            current_amount=parsed_current,
            contribution_amount=parsed_contribution,
            monthly_contribution=parsed_monthly,
        )


@tool("delete_saving_goal")
def delete_saving_goal_tool(
    goal_id: str | None = None,
    title: str | None = None,
    category: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Mevcut birikim veya tasarruf hedefini siler."""
    with SessionLocal() as db:
        return build_saving_goal_delete(
            db,
            _load_current_user(db, user_id),
            goal_id=goal_id,
            title=title,
            category=category,
        )


@tool("create_accumulation_goal")
def create_accumulation_goal_tool(
    title: str,
    target_amount: str,
    current_amount: str = "0",
    target_months: int | str = 12,
    monthly_contribution: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Belirli bir tutara ulaşmak için birikim hedefi oluşturur."""
    with SessionLocal() as db:
        try:
            parsed_target = parse_money_text(target_amount)
            parsed_current = parse_money_text(current_amount)
            parsed_monthly = (
                parse_money_text(monthly_contribution) if monthly_contribution is not None else None
            )
        except InvalidOperation:
            return {"error": "Tutarları net okuyamadım.", "title": title}
        return build_accumulation_goal_creation(
            db,
            _load_current_user(db, user_id),
            title=title,
            target_amount=parsed_target,
            current_amount=parsed_current,
            target_months=target_months,
            monthly_contribution=parsed_monthly,
        )


@tool("get_envelopes")
def get_envelopes_tool(
    slug: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Kullanıcının zarf bütçelerini listeler veya tek zarfı döner."""
    with SessionLocal() as db:
        return build_envelope_budget_overview(db, _load_current_user(db, user_id), slug=slug)


@tool("create_envelope_budget")
def create_envelope_budget_tool(
    name: str,
    budget_monthly: str,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Yeni zarf oluşturur; hazır zarf adı verilirse mevcut limiti açar/günceller."""
    with SessionLocal() as db:
        try:
            budget = parse_money_text(budget_monthly)
        except InvalidOperation:
            return {"error": "Zarf limitini net okuyamadım.", "name": name}
        return build_envelope_budget_creation(
            db,
            _load_current_user(db, user_id),
            name=name,
            budget_monthly=budget,
        )


@tool("update_envelope_budget")
def update_envelope_budget_tool(
    slug: str,
    budget_monthly: str,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Bir zarfın aylık limitini günceller."""
    with SessionLocal() as db:
        try:
            budget = parse_money_text(budget_monthly)
        except InvalidOperation:
            return {"error": "Zarf limitini net okuyamadım.", "slug": slug}
        return build_envelope_budget_update(
            db,
            _load_current_user(db, user_id),
            slug=slug,
            budget_monthly=budget,
        )


@tool("delete_envelope_budget")
def delete_envelope_budget_tool(
    slug: str,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Bir zarfı aktif profil için devre dışı bırakır; limiti 0,00 ₺ yapar."""
    with SessionLocal() as db:
        return build_envelope_budget_delete(db, _load_current_user(db, user_id), slug=slug)


@tool("create_smart_saving_plan")
def create_smart_saving_plan_tool(
    message: str,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Amaç odaklı mesajdan harcama azaltma planı ve hedefleri oluşturur."""
    with SessionLocal() as db:
        return build_smart_saving_plan(db, _load_current_user(db, user_id), message=message)


@tool("get_user_memory")
def get_user_memory_tool(
    key: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Agent'in mevcut kullanıcı için hatırladığı bilgileri döner."""
    with SessionLocal() as db:
        return build_user_memory(db, _load_current_user(db, user_id), key=key)


@tool("remember_user_memory")
def remember_user_memory_tool(
    text: str,
    key: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Açık kullanıcı onayıyla mevcut profil için güvenli hafıza kaydı yazar."""
    with SessionLocal() as db:
        return build_memory_upsert(db, _load_current_user(db, user_id), text=text, key=key)


@tool("analyze_receipt")
def analyze_receipt_tool(
    image_base64: str,
    filename: str = "receipt.jpg",
    content_type: str = "image/jpeg",
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Fiş görselini OCR ile okur. `user_id` sistem durumundan gelir."""
    with SessionLocal() as db:
        return build_receipt_candidate(
            db,
            _load_current_user(db, user_id),
            image_base64=image_base64,
            filename=filename,
            content_type=content_type,
        )


@tool("explain_concept")
def explain_concept_tool(
    concept: str,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Finansal kavramı kullanıcının seviyesine göre Türkçe açıklar."""
    with SessionLocal() as db:
        return explain_finance_concept(_load_current_user(db, user_id), concept=concept)


@tool("create_custom_lesson")
def create_custom_lesson_tool(
    topic: str,
    level: str = "beginner",
    duration_minutes: int | str = 5,
    include_examples: bool | str = True,
    include_quiz: bool | str = True,
    visual: bool | str = False,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Finans Okulu için kalıcı olmayan yapılandırılmış özel ders üretir."""
    with SessionLocal() as db:
        return build_custom_lesson(
            _load_current_user(db, user_id),
            topic=topic,
            level=level,
            duration_minutes=parse_int_text(duration_minutes, default=5, min_value=3, max_value=12),
            include_examples=parse_bool_text(include_examples, default=True),
            include_quiz=parse_bool_text(include_quiz, default=True),
            visual=parse_bool_text(visual, default=False),
        )


@tool("simulate_scenario")
def simulate_scenario_tool(
    scenario: str,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Kullanıcının verisiyle basit finansal senaryo simülasyonu döner."""
    with SessionLocal() as db:
        return simulate_finance_scenario(db, _load_current_user(db, user_id), scenario=scenario)


@tool("visualize_spending")
def visualize_spending_tool(
    days: int | str = 30,
    chart_type: str = "bar",
    category: str | None = None,
    target: str | None = None,
    targets: list[str] | None = None,
    target_type: str | None = None,
    query: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Harcama özetinden grafik üretir; chat'te inline çizilir.

    `chart_type` 'bar', 'pie' veya 'monthly' olabilir. Aylık trend için `category`,
    `target`, `targets`, `target_type` veya `query` eşleştirmesi kullanılabilir.
    Tüm veri agent state'inden gelen user_id kapsamı içindedir.
    """
    with SessionLocal() as db:
        return build_spending_chart(
            db,
            _load_current_user(db, user_id),
            days=parse_int_text(days, default=30, min_value=1, max_value=MAX_SPENDING_DAYS),
            chart_type=chart_type,
            category=category,
            target=target,
            targets=targets,
            target_type=target_type,
            query=query,
        )


@tool("visualize_saving_goals")
def visualize_saving_goals_tool(
    status: str = "active",
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Mevcut birikim ve tasarruf hedefleri için sohbet içi grafik üretir."""
    with SessionLocal() as db:
        return build_saving_goals_chart(db, _load_current_user(db, user_id), status=status)


@tool("illustrate_concept")
def illustrate_concept_tool(
    concept: str,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Finansal bir kavram için güvenli eğitim illüstrasyonu üretir.

    Yalnızca koç modunda kavram anlatımı içindir; yatırım/ürün/fiyat görselleştirme yapmaz.
    Günlük kullanıcı başına sınır uygulanır. `user_id` sistem durumundan gelir.
    """
    with SessionLocal() as db:
        return build_concept_illustration(db, _load_current_user(db, user_id), concept=concept)


TOOLS = [
    get_spending_tool,
    get_subscriptions_tool,
    create_saving_goal_tool,
    create_accumulation_goal_tool,
    update_saving_goal_tool,
    delete_saving_goal_tool,
    get_saving_goal_progress_tool,
    get_saving_goals_tool,
    get_envelopes_tool,
    create_envelope_budget_tool,
    update_envelope_budget_tool,
    delete_envelope_budget_tool,
    create_smart_saving_plan_tool,
    analyze_receipt_tool,
    explain_concept_tool,
    create_custom_lesson_tool,
    simulate_scenario_tool,
    get_user_memory_tool,
    remember_user_memory_tool,
    visualize_spending_tool,
    visualize_saving_goals_tool,
    illustrate_concept_tool,
]
