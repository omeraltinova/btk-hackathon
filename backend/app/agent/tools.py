"""Agent tool implementations backed by scoped database queries."""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Iterable
from dataclasses import dataclass
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
from app.routers.categories import (
    create_envelope_category,
    delete_envelope_category,
    set_envelope_budget,
)
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
# WHY: bare digit-length regex (CARD_NUMBER_PATTERN/TCKN_PATTERN) false-positive
# on ordinary numbers like long Turkish amounts ("12.345.678.901 ₺") or order
# IDs. We only mask when the surrounding text actually names the sensitive
# concept. IBAN/base64 patterns stay context-free because their shapes are
# already specific enough (TR-prefix + length / 80+ chars).
CARD_CONTEXT_HINTS = (
    "kart numara",
    "kart no",
    "kredi kart",
    "banka kart",
    "kartim",
    "kartimin",
)
TCKN_CONTEXT_HINTS = (
    "tckn",
    "tc kimlik",
    "kimlik no",
    "kimlik numara",
    "vatandaslik no",
)
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
    normalized = normalized.strip(".,")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "." in normalized:
        parts = normalized.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            normalized = "".join(parts)
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
    folded = _fold_control_text(text)
    if any(keyword in normalized for keyword in BLOCKED_MEMORY_KEYWORDS):
        return False
    if IBAN_PATTERN.search(text) or BASE64ISH_PATTERN.search(text):
        return False
    if CARD_NUMBER_PATTERN.search(text) and any(hint in folded for hint in CARD_CONTEXT_HINTS):
        return False
    return not (TCKN_PATTERN.search(text) and any(hint in folded for hint in TCKN_CONTEXT_HINTS))


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
    overview = build_envelope_budget_overview(db, current_user, now=now)
    envelopes = overview.get("envelopes")
    envelope = None
    if isinstance(envelopes, list):
        envelope = next(
            (item for item in envelopes if isinstance(item, dict) and item.get("slug") == slug),
            None,
        )
    if envelope is None:
        return {"error": "Zarf bulunamadı."}

    deleted = delete_envelope_category(slug=slug, db=db, current_user=current_user)
    return {
        "deleted": True,
        "slug": slug,
        "category_id": str(deleted.id)
        if deleted is not None
        else str(envelope.get("category_id", "")),
        "category_name": str(envelope.get("category_name") or "Zarf"),
    }


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
    """Return scoped recurring income/expense records and monthly equivalents."""
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
    monthly_income_total = Decimal("0")
    monthly_expense_total = Decimal("0")
    for subscription in subscriptions:
        monthly = monthly_equivalent(
            Decimal(subscription.amount),
            subscription.recurrence_interval,
            subscription.recurrence_unit,
            subscription.billing_cycle,
        )
        monthly_total += monthly
        if subscription.type == "income":
            monthly_income_total += monthly
        else:
            monthly_expense_total += monthly
        rows.append(
            {
                "id": str(subscription.id),
                "name": subscription.name,
                "merchant": subscription.merchant,
                "amount": _decimal_text(Decimal(subscription.amount)),
                "amount_formatted": format_tl(Decimal(subscription.amount)),
                "type": subscription.type,
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
        "monthly_income_total": _decimal_text(monthly_income_total),
        "monthly_income_total_formatted": format_tl(monthly_income_total),
        "monthly_expense_total": _decimal_text(monthly_expense_total),
        "monthly_expense_total_formatted": format_tl(monthly_expense_total),
        "monthly_net_total": _decimal_text(monthly_income_total - monthly_expense_total),
        "monthly_net_total_formatted": format_tl(monthly_income_total - monthly_expense_total),
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


@dataclass(frozen=True)
class _LessonContent:
    """Topic-specific lesson body. Sections are (heading, body) pairs."""

    goals: tuple[str, ...]
    sections: tuple[tuple[str, str], ...]
    examples: tuple[str, ...]
    quiz: tuple[tuple[str, str], ...]


# Rich profiles for the most-asked Turkish family finance topics.
# Adult profiles serve beginner/intermediate/advanced; child profiles override
# when the user is in the child finance level. Numeric examples use realistic
# Turkish lira figures and never recommend specific products (P7, A-4).

_LP_EMERGENCY_FUND_ADULT = _LessonContent(
    goals=(
        "Acil durum fonunun ne olduğunu ve aile bütçesinde hangi riskleri "
        "karşıladığını ayırt edebilmek.",
        "Hedef tutarı kendi geliri ve zorunlu giderleriyle hesaplayabilmek.",
        "Fonu nereye koyacağını, nasıl koruyacağını ve hangi durumlarda "
        "kullanacağını netleştirmek.",
    ),
    sections=(
        (
            "Acil durum fonu nedir?",
            "Aniden gelen iş kaybı, ciddi sağlık masrafı, kritik ev veya araç "
            "onarımı gibi planlı bütçenin dışındaki giderler için ayrılan, "
            "kolay çekilebilen tampon paradır. Yatırım değildir; nakit "
            "ihtiyacında ilk başvurulacak rezerv olarak durur.",
        ),
        (
            "Hedef tutar nasıl hesaplanır?",
            "Aylık zorunlu giderlerin (kira/aidat, fatura, market, kredi "
            "taksiti) toplamı × 3 ila 6 ay. Örnek: aylık zorunlu gider "
            "12.000 ₺ ise 36.000–72.000 ₺ makul aralıktır. Tek gelirli "
            "aileler üst banda, çift gelirli aileler alt banda yakın "
            "hedef seçer.",
        ),
        (
            "Nereye konur, ne zaman kullanılır?",
            "Anında erişilebilen, ayrı izlenebilen ve değer dalgalanması "
            "düşük bir yerde tutulur. Buradaki amaç getiri aramak değil, "
            "ihtiyaç anında paraya hızla ulaşmaktır. Sadece gerçekten "
            "beklenmeyen zorunlu giderlerde kullanılır; bayram, tatil veya "
            "doğum günü gibi planlanabilir kalemler farklı zarfta planlanır, "
            "bu fona dokunulmaz.",
        ),
        (
            "Bugünden atılacak ilk adım",
            "Aylık otomatik talimatla ücretin %5–10'unu ayrı bir hesaba "
            "aktar. İlk eşik olarak 1 aylık zorunlu gideri biriktir; "
            "sonra kademeli olarak 3 aya, sonra 6 aya çıkar.",
        ),
    ),
    examples=(
        "Mehmet ailesinin aylık zorunlu gideri 15.000 ₺. Hedef tutar "
        "3 ay × 15.000 = 45.000 ₺. Ayda 1.500 ₺ otomatik talimatla "
        "yaklaşık 30 ayda hedefe ulaşılır; mevduat faizi süreyi biraz "
        "daha kısaltır.",
        "Ayşe ailesi 8.000 ₺'lik beklenmedik diş tedavisini acil fondan "
        "öder. Aynı tutarı kredi kartı asgarisiyle ödeselerdi yaklaşık "
        "18 ay sonunda 4.000 ₺'nin üzerinde ek faiz birikecekti.",
    ),
    quiz=(
        (
            "Acil durum fonu hedef tutarı genelde nasıl hesaplanır?",
            "Aylık zorunlu giderlerin 3 ila 6 katı olarak; gelir kaynak "
            "sayısına göre alt veya üst banda yaklaşılır.",
        ),
        (
            "Bu fon yatırım amaçlı tutulur mu, planlı tatil için kullanılır mı?",
            "Hayır. Birinci özelliği anında erişilebilir olmak. Sadece "
            "beklenmedik zorunlu giderlerde kullanılır; tatil gibi "
            "planlanabilir kalemler ayrı zarfta planlanır.",
        ),
    ),
)

_LP_EMERGENCY_FUND_CHILD = _LessonContent(
    goals=(
        "Acil durum nedir ve ailede neden ekstra para tutulduğunu anlamak.",
        "Sürpriz harcama için ayrı bir kumbara veya kavanoz fikrini "
        "günlük örneklerle düşünebilmek.",
        "Bu paranın oyuncak için değil, gerçek acil ihtiyaç için ayrıldığını hatırlamak.",
    ),
    sections=(
        (
            "Acil durum nedir?",
            "Beklemediğin bir şey olduğunda — bisikletin bozulduğunda, "
            "sevdiğin biri için ilaç gerektiğinde — ailenin elindeki "
            "yedek para. Buna 'sürpriz parası' diyebilirsin.",
        ),
        (
            "Neden biriktiriyoruz?",
            "Çünkü ihtiyaç anında borç almak veya başka hayalleri ertelemek "
            "istemiyoruz. Sürpriz harcama için ayrı bir kumbara tutmak "
            "işleri kolaylaştırır.",
        ),
        (
            "Sen ne yapabilirsin?",
            "Harçlığının küçük bir parçasını (örneğin haftada 5 ₺) ayrı "
            "bir 'sürpriz parası' kumbarasına atabilirsin. Sıradan "
            "istekler için değil; sadece beklenmedik bir şey olduğunda "
            "kullanırsın.",
        ),
    ),
    examples=(
        "Diyelim ki bisikletinin tekerleği patladı, tamir 150 ₺. "
        "Önceden sürpriz kumbarana 200 ₺ koymuşsan hemen çözebilirsin.",
        "Doğum gününde 300 ₺ hediye aldın. 100 ₺'sini sürpriz kumbarasına, "
        "100 ₺'sini hayalindeki oyuncağa, 100 ₺'sini küçük günlük "
        "isteklere ayırabilirsin.",
    ),
    quiz=(
        (
            "Sürpriz parası ne için ayrılır?",
            "Beklemediğin bir şey olduğunda — bozulan bir eşya, küçük "
            "bir tamir veya başka acil ihtiyaç için.",
        ),
        (
            "Bu parayı oyuncak almak için kullanır mıyız?",
            "Hayır, çünkü oyuncak planlanabilir bir istek. Sürpriz "
            "parası gerçekten beklemediğin durumlar içindir.",
        ),
    ),
)

_LP_INTEREST_ADULT = _LessonContent(
    goals=(
        "Faizin para üzerinde zamanla nasıl çalıştığını ve mevduat ile "
        "kredi taraflarındaki yönünü ayırt edebilmek.",
        "Yıllık ve aylık faiz arasındaki dönüşümü kabaca yapabilmek.",
        "Faizin aile bütçesinde hangi karalara dokunduğunu görmek "
        "(birikim hızı, borç maliyeti, hedef süresi).",
    ),
    sections=(
        (
            "Faiz nedir?",
            "Para zamanla bir maliyet veya getiri taşır. Bankaya para "
            "yatırdığında banka sana, krediyi kullandığında sen bankaya "
            "faiz ödersin. Türkiye'de faiz oranları genelde yıllık "
            "ifade edilir; aylık etkisi kabaca yıllık oranın 12'ye "
            "bölümüdür.",
        ),
        (
            "Mevduat vs kredi faizi",
            "Mevduat faizi senin yararına çalışır: 10.000 ₺'yi yıllık "
            "%40 brüt faizle 1 yıl tutarsan, vergi düşmeden önce yaklaşık "
            "4.000 ₺ getiri görürsün. Kredi faizi tersine çalışır: aynı "
            "10.000 ₺ borçluyken yıllık %60 faiz oranıyla 1 yıl sonunda "
            "yaklaşık 16.000 ₺ ödeme yapman gerekebilir.",
        ),
        (
            "Bütçeye nasıl dokunur?",
            "Faiz birikim hedeflerini hızlandırır, borç yükünü ağırlaştırır. "
            "Yüksek kredi kartı faizi ödüyorsan, aynı parayı birikime "
            "yönlendirmek genelde daha hızlı kazandırır — çünkü kredi "
            "kartı faizi mevduat faizinden çok daha yüksek olur.",
        ),
    ),
    examples=(
        "Bir aile aylık 1.000 ₺'yi yıllık %35 net mevduat faiziyle 24 ay "
        "biriktirir. Toplam yatırım 24.000 ₺ olur, biriken bakiye yaklaşık "
        "33.000 ₺ civarında çıkar (basit hesapla).",
        "Aynı aile 24.000 ₺ kredi kartı borcunu yıllık %85 faizle ödese, "
        "asgari ödemeyle borç çok daha yavaş azalır ve ek faiz toplamı "
        "12 ay içinde rahatlıkla 10.000 ₺'nin üzerine çıkabilir.",
    ),
    quiz=(
        (
            "Yıllık %48 faiz oranı kabaca aylık ne kadar eder?",
            "Yaklaşık aylık %4 (48 ÷ 12). Bileşik etki dahil edilince biraz daha yüksek çıkar.",
        ),
        (
            "Faiz öderken mi yoksa kazanırken mi para senin yararına çalışır?",
            "Kazanırken (mevduat). Öderken (kredi/kredi kartı) faiz aile bütçesinden çıkar.",
        ),
    ),
)

_LP_INTEREST_CHILD = _LessonContent(
    goals=(
        "Faizin 'paranın zamanla büyümesi' olduğunu somut bir hikâyeyle anlamak.",
        "Kumbara ve mevduat hesabı arasındaki farkı dondurma veya oyuncak örneğiyle düşünmek.",
        "Küçük tutarların zamanla nasıl büyüdüğünü görmek.",
    ),
    sections=(
        (
            "Faiz nedir?",
            "Diyelim ki bankaya 100 ₺ koydun. Banka 'bana bir yıl bıraktığın "
            "için sağ ol' deyip sana 30 ₺ daha ekledi. İşte bu eklenen "
            "para, faiz. Para zamanla seninle birlikte çalışmış oldu.",
        ),
        (
            "Kumbara ile fark",
            "Kumbarada 100 ₺ koyduğunda yıl sonunda hâlâ 100 ₺ olur. "
            "Bankada faizle birlikte 130 ₺ olur. Ama kumbara da iyidir: "
            "her hafta düzenli koymaya alıştırır.",
        ),
        (
            "Sabırlı olmak işe yarıyor",
            "Faiz küçükken büyük değildir; ama sabırla beklersen küçük "
            "tutarlar bile zamanla büyüyebilir. İki yıl beklediğinde 100 ₺ "
            "yaklaşık 170 ₺'ye yakın olabilir.",
        ),
    ),
    examples=(
        "Doğum gününde 200 ₺ aldın. 100 ₺'sini bankaya koysan, bir yıl "
        "sonra yaklaşık 130 ₺ olabilir. Yani 30 ₺ kazanmış olursun.",
        "Eğer her ay harçlığından 50 ₺ ayırıp banka hesabına koyarsan, "
        "yıl sonunda hem biriktirdiğin 600 ₺ hem de faizden gelen "
        "ekstra para birikir.",
    ),
    quiz=(
        (
            "Bankaya 100 ₺ koyduğun zaman ne olur?",
            "Bir süre sonra banka teşekkür olarak ekstra para ekler. Bu ekstra paraya faiz denir.",
        ),
        (
            "Kumbarada para faizle büyür mü?",
            "Hayır, kumbara faiz vermez. Ama düzenli para atma alışkanlığı kazandırır.",
        ),
    ),
)

_LP_COMPOUND_INTEREST_ADULT = _LessonContent(
    goals=(
        "Bileşik faizin 'faizin faizi' olduğunu ve süre ile çarpıldığında "
        "nasıl hızlandığını görmek.",
        "Basit faiz ile bileşik faizi sayısal bir örnekle ayırt edebilmek.",
        "Bileşik etkiyi birikim hedefinde ve borç yönetiminde değerlendirebilmek.",
    ),
    sections=(
        (
            "Bileşik faiz nedir?",
            "Anaparan ürettiği faiz tekrar anaparaya eklenir; bir sonraki "
            "dönem faiz, bu yeni ve büyümüş anapara üzerinden işler. "
            "Formül: Son tutar = Anapara × (1 + faiz oranı) ^ dönem sayısı.",
        ),
        (
            "Basit faiz ile farkı",
            "Basit faiz her dönem sadece ilk anapara üzerinden hesaplanır. "
            "Bileşik faiz, kazanılan faizi de dahil eder. Süre uzadıkça "
            "fark büyür: kısa vadede ufak, uzun vadede çok belirgin olur.",
        ),
        (
            "Bütçe ve hedef açısından önemi",
            "Birikim tarafında bileşik faiz hedefe daha çabuk götürür. "
            "Borç tarafında ise (özellikle kredi kartı, ihtiyaç kredisi) "
            "bileşik etki ödenecek toplam tutarı sessizce büyütür. Bu "
            "yüzden yüksek faizli borçları erken kapatmak önemli olur.",
        ),
    ),
    examples=(
        "10.000 ₺ anaparayı yıllık %40 bileşik faizle 5 yıl tutarsan: "
        "10.000 × 1,40 ^ 5 ≈ 53.782 ₺. Aynı dönemde basit faizle "
        "yaklaşık 30.000 ₺ olurdu — bileşik etki yaklaşık 23.000 ₺ "
        "fazladan kazandırır (vergi etkisi hariç, eğitsel hesap).",
        "Bir aile 24.000 ₺ kredi kartı borcunu sadece asgariyle ödediğinde, "
        "aylık bileşik faiz etkisiyle 18 ay sonunda toplam ödenecek tutar "
        "kolayca 33.000 ₺'yi geçebilir.",
    ),
    quiz=(
        (
            "Bileşik faiz formülü nedir?",
            "Son tutar = Anapara × (1 + faiz oranı) ^ dönem sayısı.",
        ),
        (
            "Süre uzadıkça bileşik etki nasıl davranır?",
            "Üstel olarak büyür; ilk yıllarda küçük görünür, sonraki "
            "yıllarda kazanç (veya borç) hızı belirgin artar.",
        ),
    ),
)

_LP_INFLATION_ADULT = _LessonContent(
    goals=(
        "Enflasyonun fiyatlar genel seviyesindeki artış olduğunu ve alım "
        "gücünü nasıl aşındırdığını anlamak.",
        "TÜFE (Tüketici Fiyat Endeksi) kavramının ne ölçtüğünü görmek.",
        "Aile bütçesinde enflasyon karşısında hangi kararların önem kazandığını ayırt etmek.",
    ),
    sections=(
        (
            "Enflasyon nedir?",
            "Mal ve hizmetlerin ortalama fiyatlarının zamanla yükselmesidir. "
            "Aynı 100 ₺ ile geçen yıl daha fazla ürün alabiliyorduysan ve "
            "bu yıl daha az alabiliyorsan, paranın alım gücü düşmüş "
            "demektir.",
        ),
        (
            "TÜFE neyi ölçer?",
            "TÜİK her ay bir 'sepet' (market, kira, ulaşım, eğitim, "
            "sağlık vb. kalemler) belirleyip fiyat değişimini izler. Yıllık "
            "TÜFE %40 dediğimizde, ortalama sepetin geçen yıla göre %40 "
            "pahalandığını söylüyoruz.",
        ),
        (
            "Bütçeye etkisi ve karar noktaları",
            "Sabit gelirli bir aile, gelir artışı enflasyonun gerisinde "
            "kalırsa reel olarak fakirleşir. Bu yüzden gider zarflarını "
            "düzenli güncellemek, tekrarlayan ödemeleri yıllık olarak "
            "gözden geçirmek ve birikim hedefini enflasyonu göz önünde "
            "bulundurarak ayarlamak önemli olur.",
        ),
    ),
    examples=(
        "Bir ekmek geçen yıl 5 ₺, bu yıl 8 ₺ olduysa o kalemde fiyat "
        "artışı %60. Aile bütçesindeki market zarfında bunu görmezden "
        "gelmek, ay sonu açığını gizler.",
        "Aylık 18.000 ₺ giderle yaşayan bir aile, yıllık %50 TÜFE "
        "ortamında bir sonraki yıl aynı yaşam standardı için yaklaşık "
        "27.000 ₺'ye ihtiyaç duyacak.",
    ),
    quiz=(
        (
            "Alım gücü ne demek?",
            "Aynı parayla satın alınabilecek mal ve hizmet miktarı. "
            "Enflasyon yüksek olduğunda aynı para daha az şey alır.",
        ),
        (
            "Enflasyon karşısında bütçede hangi pratik adım atılır?",
            "Zarf bütçesini düzenli güncellemek, tekrarlayan ödemeleri "
            "yılda en az bir kez gözden geçirmek ve birikim katkısını "
            "fiyat artışına göre ayarlamak.",
        ),
    ),
)

_LP_BUDGET_ADULT = _LessonContent(
    goals=(
        "Aile bütçesinin gelir-gider tablosundan daha fazlası olduğunu, "
        "zarf metoduyla nasıl yönetildiğini görmek.",
        "50/30/20 gibi pratik bir paylaştırma kuralını kavramak.",
        "Ay başı plan ve ay sonu denge tablosu döngüsünü kurmak.",
    ),
    sections=(
        (
            "Bütçenin amacı",
            "Bütçe, paranın nereye gittiğini takip etmek değil; nereye "
            "gideceğine önceden karar vermektir. Aile bütçesinde temel "
            "bölmeler 'zorunlu giderler', 'planlı istekler' ve 'birikim' "
            "şeklinde düşünülebilir.",
        ),
        (
            "Zarf metodu",
            "Net gelir aylık olarak zarflara bölünür: Market, Fatura, Okul, "
            "Ulaşım, Harçlık, Birikim. Her zarfın kendi limiti vardır. "
            "Bir zarf bitince diğerine 'borç verilebilir' ama bunun "
            "kayıtla, planla yapılması gerekir; yoksa kontrol kaybolur.",
        ),
        (
            "50/30/20 kuralı",
            "Net gelirin %50'si zorunlu giderler, %30'u istek/yaşam "
            "kalitesi, %20'si birikim ve borç kapatma olarak ayrılır. "
            "Türkiye gibi yüksek enflasyon olan ülkelerde bu oranları "
            "aileye göre uyarlamak gerekir; ama temel fikir 'birikim "
            "kendine pay ayırır' olmasıdır.",
        ),
        (
            "Aylık döngü",
            "Ay başı: zarflara para ayır, otomatik talimatları kontrol et. "
            "Hafta sonları: zarf bakiyelerine bak, gerekirse küçük "
            "düzeltme yap. Ay sonu: gerçekleşen tablo ile plan arasındaki "
            "farkı yaz, ne öğrendiğine bir cümleyle karar ver.",
        ),
    ),
    examples=(
        "Net gelir 30.000 ₺ olan bir ailede %50/30/20 yaklaşımı: "
        "15.000 ₺ zorunlu, 9.000 ₺ planlı istek, 6.000 ₺ birikim ve borç. "
        "Aile yüksek kirayla yaşıyorsa zorunlu oran %60'a çıkabilir; "
        "birikim oranı düşse bile sıfırlanmaması önerilir.",
        "Market zarfı 4.000 ₺ ayrılan bir ailede 25. gün 3.700 ₺ "
        "harcanmışsa, kalan 5 gün için günlük yaklaşık 60 ₺ güvenli "
        "harcama hedeflenebilir.",
    ),
    quiz=(
        (
            "Zarf bütçesinin temel fikri nedir?",
            "Her gider kategorisine ay başından önceden bir limit ayırıp "
            "ay içinde o limit içinde kalmaya çalışmak.",
        ),
        (
            "50/30/20 kuralında %20 nereye gider?",
            "Birikim ve borç kapatmaya. Bu pay aile dışında kalan tüm "
            "harcama baskısına rağmen korunmaya çalışılır.",
        ),
    ),
)

_LP_SAVINGS_HABIT_ADULT = _LessonContent(
    goals=(
        "Tasarrufun bir tutar değil, alışkanlık olduğunu görmek.",
        "Ay başı / ay sonu arasındaki farkı anlamak ve otomatik talimatın "
        "neden işe yaradığını kavramak.",
        "Küçük ama düzenli adımların yıllık etkisini somut hesapla değerlendirmek.",
    ),
    sections=(
        (
            "Tasarruf neden zor?",
            "Ay sonunda 'kalanı biriktiririm' yaklaşımı genelde başarısız "
            "olur, çünkü harcamalar gelirin tamamını doldurma eğilimindedir. "
            "Bu yüzden tasarruf önce, harcama sonra yaklaşımı daha "
            "sürdürülebilirdir.",
        ),
        (
            "Otomatik talimatın gücü",
            "Maaş gününün ertesi günü, belirli bir tutarı (örneğin gelirin "
            "%10'u) ayrı bir hesaba otomatik aktaran bir talimat tanımla. "
            "Bu yöntemde tasarruf bir karar değil, varsayılan davranıştır.",
        ),
        (
            "Küçük tutarların etkisi",
            "Ayda 500 ₺ otomatik birikim yıllık 6.000 ₺ eder. Yıllık ortalama "
            "%30 net faizle 5 yıl sonunda yaklaşık 56.000 ₺'ye yaklaşır. "
            "Tutar küçükken bile süre etkisi hissedilir.",
        ),
    ),
    examples=(
        "Aylık 600 ₺ otomatik tasarruf yapan bir aile, 12 ay sonunda "
        "7.200 ₺ + faiz eder; bu tutar 1 aylık zorunlu giderini bile "
        "karşılayan bir başlangıç tamponuna dönüşebilir.",
        "Aynı aile, abonelik gözden geçirmesiyle aylık 250 ₺ tasarruf "
        "ekler. Yeni toplam ayda 850 ₺ olur; yıllık etkisi yaklaşık "
        "3.000 ₺ artar.",
    ),
    quiz=(
        (
            "Tasarruf neden 'önce ayır, sonra harca' biçiminde kurulur?",
            "Çünkü harcama, gelirin tamamını dolduracak şekilde "
            "şekillenir. Önceden ayırmadığında ay sonunda biriken "
            "tutar genelde sıfıra yakın çıkar.",
        ),
        (
            "Otomatik talimat ne işe yarar?",
            "Tasarrufu kararla değil, varsayılan davranışla yapar; irade testini ortadan kaldırır.",
        ),
    ),
)

_LP_MIN_PAYMENT_ADULT = _LessonContent(
    goals=(
        "Kredi kartı asgari ödemenin ne anlama geldiğini ve neden tuzak olabileceğini anlamak.",
        "Asgari ödemeyle borcun zaman içinde nasıl şişebildiğini sayısal olarak görmek.",
        "Borç kapatmada hangi yaklaşımların daha hızlı ilerlettiğini ayırt etmek.",
    ),
    sections=(
        (
            "Asgari ödeme nedir?",
            "Kredi kartı ekstresinde belirtilen ve gecikme/yasal işleme "
            "düşmemek için yapman gereken en düşük ödeme. Türkiye'de "
            "bankalar tarafından genellikle ekstre tutarının belirli "
            "yüzdesi olarak hesaplanır.",
        ),
        (
            "Faiz nasıl çalışır?",
            "Sadece asgariyi ödediğinde kalan borç bakiyesi bir sonraki "
            "ay tekrar faizlenir. Türkiye'de kredi kartı faizleri "
            "yüksek seyrettiği için ay ay birikip bileşik etkiyle "
            "büyür.",
        ),
        (
            "Pratik çıkış stratejisi",
            "Mümkünse asgarinin üzerinde ödeme yap — sabit aylık ek "
            "tutar belirle (örneğin asgari + 1.000 ₺) ve düzenli "
            "öde. Birden fazla borcu olan bir aile için 'çığ' "
            "(en yüksek faizli önce) veya 'kartopu' (en küçük "
            "borç önce) yaklaşımları yaygındır.",
        ),
    ),
    examples=(
        "8.400 ₺ kredi kartı borcu yıllık yaklaşık %85 faiz (aylık ~%5,3) "
        "ile sadece asgari (~%20) ödenirse, 18 ay sonunda ödenen toplam "
        "faiz 4.700 ₺'yi rahatlıkla geçer.",
        "Aynı 8.400 ₺ borçta aylık 1.000 ₺ ek ödeme yapılırsa, borç "
        "yaklaşık 10–12 ay içinde tamamen kapanır ve ödenen toplam "
        "faiz birkaç bin lira azalır.",
    ),
    quiz=(
        (
            "Asgari ödeme yapmak borcu kapatır mı?",
            "Hayır; sadece gecikmeyi önler. Kalan bakiye faizlenmeye "
            "devam eder ve borç bileşik etkiyle uzayabilir.",
        ),
        (
            "Birden fazla borçta hangi yaklaşımlar var?",
            "Çığ yöntemi (en yüksek faizli borca odaklan) ve kartopu "
            "yöntemi (en küçük bakiyeli borca odaklan). Hangisinin "
            "daha sürdürülebilir olduğu ailenin motivasyonuna göre "
            "değişir.",
        ),
    ),
)

_LP_SUBSCRIPTION_ADULT = _LessonContent(
    goals=(
        "Abonelik (Netflix, Spotify, dergi, dijital servisler) gibi "
        "tekrarlayan ödemelerin aylık ve yıllık etkisini görmek.",
        "Kullanım skoru kavramını anlamak: ödediğin tutara karşılık "
        "gerçekten ne kadar faydalanıyorsun?",
        "Ay sonu yerine yılda bir 'abonelik temizliği' alışkanlığını kurmak.",
    ),
    sections=(
        (
            "Aboneliklerin gizli etkisi",
            "Küçük tutarlar (örneğin 50–150 ₺) tek başına büyük "
            "görünmez ama bir araya geldiğinde aylık birkaç yüz ₺ "
            "etkiye ulaşır. Yıllığa çevrildiğinde tutar net "
            "şekilde fark edilir.",
        ),
        (
            "Kullanım skoru",
            "Bir aboneliği son 90 günde kaç kez kullandığını düşün. "
            "Hiç kullanmıyorsan skor düşüktür ve maliyet boşa "
            "gidiyor demektir. 'Belki ileride lazım olur' "
            "yaklaşımı yıllık 1.000 ₺'lik kayıplara yol açabilir.",
        ),
        (
            "Yıllık temizlik alışkanlığı",
            "Yılda bir kez (örneğin yıl başında) tüm aktif aboneliklerini "
            "listele. Üç soruyu sor: son 90 günde kaç kez kullandım, "
            "alternatif daha ucuz mu, gerçekten gerekli mi? Bu kontrolle "
            "ailenin yıllık birkaç bin ₺ tasarruf etmesi sıradandır.",
        ),
    ),
    examples=(
        "Aylık 230 ₺ olan bir dijital servis yıllık 2.760 ₺ eder. Eğer "
        "ayda 1–2 kez kullanılıyorsa, kullanım başına maliyet 100–230 ₺ "
        "civarına çıkar.",
        "Bir ailenin 4 farklı dijital servisi var: aylık toplam 720 ₺, "
        "yıllık 8.640 ₺. İki tanesi 90 gündür kullanılmıyor; iptal "
        "edilirse aylık 380 ₺ tasarruf, yıllık ~4.500 ₺.",
    ),
    quiz=(
        (
            "Kullanım skoru ne işe yarar?",
            "Bir aboneliğin ödediğin paraya kıyasla gerçek faydasını "
            "ölçer. Düşük skorlu abonelikler iptal adayıdır.",
        ),
        (
            "Aboneliği aylık değil yıllık tutarla düşünmek neden faydalı?",
            "Çünkü küçük tutarlar yıllığa çevrildiğinde gerçek "
            "büyüklüğü daha net görünür ve karar vermek kolaylaşır.",
        ),
    ),
)

_LP_DIVERSIFICATION_ADULT = _LessonContent(
    goals=(
        "Çeşitlendirmenin neden 'tüm yumurtaları aynı sepete koyma' kuralı olduğunu kavramak.",
        "Risk dağıtmanın aile bütçesinde — yatırım değil bütçe yapısında — "
        "nasıl uygulanabileceğini görmek.",
        "Çeşitlendirmenin neden ürün seçimi değil, plan çeşidi olduğunu anlamak (eğitim amaçlı).",
    ),
    sections=(
        (
            "Çeşitlendirme nedir?",
            "Bir riskin tek bir kaynağa bağımlı olmamasıdır. Aile "
            "bütçesinde örneğin tek gelirden çift gelire geçmek, tek "
            "para birimine değil farklı zarflara hedef koymak, ya da "
            "acil durum fonunu farklı vade/erişim seviyelerinde "
            "tutmak çeşitlendirmeye örnektir.",
        ),
        (
            "Neden işe yarar?",
            "Tek kaynaklı planlar tek bir olumsuzlukta tüm dengeyi bozar. "
            "Çeşitlendirilmiş planda bir koldaki dalgalanma diğeriyle "
            "dengelenir; ailenin nakit akışı daha öngörülebilir olur.",
        ),
        (
            "Önemli sınır: tavsiye değil",
            "Bu ders belirli bir ürün, fon, hisse, kripto, altın veya "
            "döviz alımını/satımını önermez. Çeşitlendirmenin nasıl bir "
            "düşünce yapısı olduğunu açıklar; somut yatırım kararları "
            "için lisanslı uzman görüşü gerekir.",
        ),
    ),
    examples=(
        "Aylık geliri yalnızca tek bir kaynaktan gelen bir aile, ikinci "
        "küçük bir gelir akışı (freelance iş, kira geliri, ek "
        "ücretli ders) kurarak risklerini dağıtabilir.",
        "Birikim hedefi olan bir aile, hedefin tamamını tek bir araçta "
        "değil; bir kısmını acil durum fonu için likit hesapta, bir "
        "kısmını uzun vadeli birikim için ayrı bir hesapta tutarak "
        "zaman ve erişim çeşitliliği sağlar.",
    ),
    quiz=(
        (
            "Çeşitlendirme tek başına garantili kazanç verir mi?",
            "Hayır. Risk dağıtmak, kayıp olasılığını kontrollü tutmak "
            "için kullanılır; getiri vaadi içermez.",
        ),
        (
            "Bu ders hangi ürünü almanı söyler?",
            "Hiçbirini. Eğitim amaçlıdır; belirli ürün, fon, hisse veya kripto tavsiyesi yapılmaz.",
        ),
    ),
)


_LP_MONEY_MARKET_FUND_ADULT = _LessonContent(
    goals=(
        "Para piyasası fonunun ne olduğunu, neden mevduat veya hisse gibi "
        "düşünülmemesi gerektiğini ayırt etmek.",
        "Günlük nakit yönetimi, acil durum fonu ve kısa vadeli hedefler "
        "arasında nasıl bir karar çerçevesi kurulduğunu görmek.",
        "Getiri, erişim süresi, vergi, masraf ve risk başlıklarını ürün "
        "seçmeden önce hangi sorularla kontrol edeceğini öğrenmek.",
    ),
    sections=(
        (
            "Para piyasası fonu nedir?",
            "Para piyasası fonu, çok kısa vadeli ve görece düşük dalgalı para "
            "piyasası araçlarından oluşan bir yatırım fonu türüdür. İçinde "
            "genellikle repo, ters repo, kısa vadeli borçlanma araçları veya "
            "mevduata benzer nakit yönetimi araçları bulunabilir. Kullanıcının "
            "gözünde çoğu zaman 'boşta duran parayı günlük değerlendirme' fikriyle "
            "anılır; ama bu, paranın tamamen risksiz veya bankadaki vadesiz hesapla "
            "aynı olduğu anlamına gelmez. Fonun fiyatı günlük değişebilir, getirisi "
            "garanti değildir ve fonun içeriği fon yöneticisinin stratejisine göre "
            "değişebilir.",
        ),
        (
            "Aile bütçesinde hangi ihtiyaca dokunur?",
            "Bu konu en çok 'kısa süre sonra kullanacağım parayı nerede takip "
            "etmeliyim?' sorusuna dokunur. Örneğin kira, okul taksiti, kredi kartı "
            "son ödeme tarihi veya birkaç ay sonra yapılacak tatil harcaması gibi "
            "yakın vadeli paralar için asıl mesele yüksek getiri aramak değil, paraya "
            "zamanında ulaşabilmek ve bütçe planını bozmamaktır. Bu yüzden para "
            "piyasası fonu konuşurken önce 'bu para ne zaman lazım, kayıp yaşasam "
            "planım bozulur mu, aynı gün nakde dönmem gerekir mi?' soruları sorulur.",
        ),
        (
            "Mevduat, vadesiz hesap ve risk farkı",
            "Vadesiz hesap erişim açısından rahattır ama genelde getiri üretmez. "
            "Vadeli mevduat belirli bir süre kilitlenebilir ve bankanın sunduğu "
            "oranla çalışır. Para piyasası fonunda ise fon payı alırsın; getiriyi "
            "önceden kesin bilmezsin, fon fiyatı günlük oluşur ve emir saatine göre "
            "nakde dönüş süresi değişebilir. Kısa vadeli ve düşük dalgalı araçlar "
            "kullanıldığı için risk profili birçok yatırım aracına göre daha sakin "
            "olabilir; yine de 'ana para kesin korunur' diye düşünmek doğru değildir.",
        ),
        (
            "Karar verirken kontrol listesi",
            "Belirli bir fon adı seçmeden önce şu kontrol listesiyle düşün: Paraya "
            "hangi tarihte ihtiyacım var? Fonun alım-satım saatleri ve nakde dönüş "
            "süresi bütçeme uyuyor mu? Yönetim ücreti, stopaj/vergi ve geçmiş "
            "dalgalanma benim için anlaşılır mı? Bu para acil durum fonunun tamamı mı, "
            "yoksa kısa vadeli hedefin küçük bir parçası mı? Cevaplar net değilse konu "
            "ürün seçimine değil, önce nakit akışı planını sadeleştirmeye dönmelidir.",
        ),
    ),
    examples=(
        "Bir aile 2 ay sonra 20.000 ₺ okul taksiti ödeyecek. Bu para için ana "
        "soru 'en yüksek getiriyi nerede bulurum?' değil; 'ödeme gününde paraya "
        "sorunsuz ulaşabilir miyim ve dalgalanma olursa bütçem bozulur mu?' "
        "sorusudur. Bu çerçeve, para piyasası fonunu bir getiri vaadi değil, "
        "nakit yönetimi aracı olarak değerlendirmeye yardım eder.",
        "Acil durum fonu 60.000 ₺ olan bir aile, bu tutarın tamamını tek yerde "
        "tutmak yerine erişim ihtiyacını düşünür: bir kısmı aynı gün erişilebilir "
        "hesapta, bir kısmı kısa vadeli nakit yönetimi aracında izlenebilir. Bu "
        "örnek bir ürün önerisi değil; erişim süresi ve risk ayrımını gösteren "
        "eğitsel bir çerçevedir.",
    ),
    quiz=(
        (
            "Para piyasası fonu vadesiz hesapla aynı şey midir?",
            "Hayır. Fon payının fiyatı günlük oluşur; getiri garanti değildir "
            "ve nakde dönüş süresi fon/işlem saatlerine bağlı olabilir.",
        ),
        (
            "Kısa vadeli para için ilk sorulacak soru nedir?",
            "Bu paraya ne zaman ihtiyacım var ve o tarihte nakde ulaşamazsam "
            "bütçe planım bozulur mu?",
        ),
    ),
)


_LP_INCOME_EXPENSE_ADULT = _LessonContent(
    goals=(
        "Gelir ve giderin sadece bir tablo değil, ay başı/ay sonu döngüsü olduğunu görmek.",
        "Sabit vs değişken kalemleri ayırmak.",
        "Aylık denge tablosunu hızlıca okuyabilmek.",
    ),
    sections=(
        (
            "Gelir tarafı",
            "Net maaş, ek iş, kira geliri, harçlık, freelance, hediye "
            "gibi kaynakların ay içinde ne zaman geldiğini bilmek "
            "ödeme planını netleştirir. Sabit gelir (maaş) ve "
            "değişken gelir (freelance, prim) ayrı düşünülmelidir.",
        ),
        (
            "Gider tarafı",
            "Sabit giderler: kira, fatura, kredi taksiti, abonelikler. "
            "Değişken giderler: market, ulaşım, eğlence, yemek. "
            "Sabit giderler genelde gelir gününe yakın planlanırken "
            "değişken giderler ay içine yayılır.",
        ),
        (
            "Aylık denge tablosu",
            "Net gelir – sabit giderler – değişken giderler – birikim = "
            "ay sonu kalan. Bu kalan sıfıra yakınsa bütçe gergin "
            "demektir; eksiye düşüyorsa zarf metodu veya gider "
            "gözden geçirme adımı atılmalıdır.",
        ),
    ),
    examples=(
        "Net gelir 28.000 ₺ olan bir ailede: sabit giderler 14.000 ₺, "
        "değişken giderler 9.000 ₺, birikim 3.000 ₺. Ay sonu kalan "
        "2.000 ₺; bu rezerv ay içi sürprizleri karşılar.",
        "Aynı ailede bir abonelik yenilemesi sabit giderleri 14.500 ₺'ye "
        "çıkarsa, birikim payını azaltmadan değişken giderlerden "
        "500 ₺ tasarruf hedefi gerekir.",
    ),
    quiz=(
        (
            "Sabit ve değişken gider farkı nedir?",
            "Sabit gider tutarı aydan aya neredeyse aynı kalan kalemlerdir "
            "(kira, abonelik). Değişken gider tutarı her ay farklı olabilen "
            "kalemlerdir (market, ulaşım, eğlence).",
        ),
        (
            "Ay sonu kalan eksiye düşüyorsa ilk hangi adım atılır?",
            "Zarf bütçesini güncelleyip sabit giderlerden veya "
            "tekrarlayan ödemelerden başlayarak gözden geçirmek.",
        ),
    ),
)

_LP_STATEMENT_READING_ADULT = _LessonContent(
    goals=(
        "Kredi kartı ekstresinin temel alanlarını tanımak.",
        "Asgari, son ödeme tarihi, ekstre tarihi, dönem borcu gibi kavramları ayırt etmek.",
        "Ekstrede gizli kalan tekrarlayan ödemeleri fark etmek.",
    ),
    sections=(
        (
            "Ekstre nedir?",
            "Kredi kartı işlemlerinin bir aylık döneme sıkıştırılmış "
            "raporu. Ekstre tarihi (kesim günü), son ödeme tarihi, "
            "dönem borcu ve asgari ödeme tutarı en kritik bilgilerdir.",
        ),
        (
            "Temel alanlar",
            "Ekstre tarihi: işlemlerin kesildiği gün. Son ödeme tarihi: "
            "geç kalmadan ödeme yapılması gereken son gün (genelde "
            "ekstre tarihinden 10 gün sonra). Dönem borcu: bu ekstrede "
            "ödenecek toplam. Asgari: gecikmeden kurtulmak için en az "
            "ödenmesi gereken tutar.",
        ),
        (
            "Tekrarlayan ödemeleri yakalamak",
            "Ekstrede her ay benzer satıcıdan benzer tutarda görülen "
            "satırlar genelde abonelik veya otomatik ödemedir. Bunları "
            "ayrı bir kontrol listesinde tut; yılda bir kez gerçekten "
            "kullanılıp kullanılmadığını sor.",
        ),
    ),
    examples=(
        "Ekstre tarihi her ayın 5'i olan bir kartta son ödeme tarihi "
        "genelde 15'i civarındadır. Bu tarihten önce yapılan ödeme "
        "faiz veya gecikme cezası yaratmaz.",
        "Bir aile ekstrede üç ay üst üste 230 ₺ olarak görünen bir "
        "satırı fark ediyor: aslında 2 yıldır kullanılmayan bir "
        "dijital servis. İptal ile yıllık 2.760 ₺ tasarruf doğar.",
    ),
    quiz=(
        (
            "Son ödeme tarihi ne anlama gelir?",
            "Gecikme faizi veya cezası doğmadan ödeme yapılması gereken "
            "son gün. Bu tarihten sonra ödeme yapılırsa ek maliyet "
            "doğar.",
        ),
        (
            "Aynı satıcıdan her ay aynı tutarda işlem görülürse ne ihtimal?",
            "Büyük olasılıkla bir abonelik veya otomatik ödeme; gerçekten "
            "kullanılıyor mu diye yıllık kontrol önerilir.",
        ),
    ),
)

_LP_ALLOWANCE_CHILD = _LessonContent(
    goals=(
        "Harçlığın 'serbest para' değil, planlanabilir bir kaynak olduğunu görmek.",
        "Harçlığı 'şimdi harca', 'biriktir' ve 'paylaş' gibi üç küçük "
        "bölmeye ayırma fikrini denemek.",
        "Bir hafta sonunda kendi cebine bakıp ne öğrendiğini söylemek.",
    ),
    sections=(
        (
            "Harçlık nedir?",
            "Ailenin sana belirli bir süre için verdiği para. Bu para "
            "senin küçük kararlarını öğrenmen için. Geldiği anda hemen "
            "bitirmek zorunda değilsin; bir kısmını saklayabilirsin.",
        ),
        (
            "Üç bölmeli kumbara",
            "Aldığın 100 ₺ harçlığı üç parçaya böl: 50 ₺ şu hafta için "
            "(istediğin küçük şeyler), 30 ₺ biriktirmek için (büyük bir "
            "hayal), 20 ₺ paylaşmak veya beklenmedik durum için. Tutar "
            "küçükse oranı koru.",
        ),
        (
            "Hafta sonu küçük kontrol",
            "Hafta sonunda kumbarana bak: planına ne kadar uydun? "
            "Bir sonraki hafta için bir şey değiştirmek ister misin? "
            "Bu konuşma anne baban ile yapılırsa daha eğlenceli olur.",
        ),
    ),
    examples=(
        "Hayalindeki oyuncak 600 ₺. Haftalık 30 ₺ biriktirirsen "
        "yaklaşık 20 haftada (5 ayda) hedefe ulaşırsın. Eğer doğum "
        "günü hediyesinden bir miktar eklersen süre kısalır.",
        "Bu hafta harçlığının 50 ₺'sini hemen harcadın, 30 ₺'sini "
        "kumbaraya attın, 20 ₺'sini doğum günü hediyesi için "
        "ayırdın. Önümüzdeki hafta planını biraz değiştirebilirsin.",
    ),
    quiz=(
        (
            "Harçlığın tamamını hemen harcamak zorunda mısın?",
            "Hayır. Bir kısmını biriktirip daha büyük bir hayal için kullanabilirsin.",
        ),
        (
            "Üç bölmeli kumbarada üç bölme genelde ne için?",
            "Şimdi harcamak için, biriktirmek için ve paylaşmak veya sürpriz harcama için.",
        ),
    ),
)

_LP_NEED_WANT_CHILD = _LessonContent(
    goals=(
        "İhtiyaç ile istek arasındaki farkı somut bir örnekle ayırmak.",
        "Kantin alışverişinde veya çevrimiçi alışverişte küçük bir kontrol soru ezberlemek.",
        "Karar verirken kumbara hedefini de düşünmeye alışmak.",
    ),
    sections=(
        (
            "İhtiyaç nedir?",
            "Olmadan zorlanacağın şey. Mesela okul için kalem ya da defter "
            "ihtiyaçtır. İhtiyaçlar genelde 'bu olmazsa ne olur?' sorusunun "
            "cevabıyla 'işim çok zorlaşır' olur.",
        ),
        (
            "İstek nedir?",
            "Olmasını çok istediğin ama olmadan idare edebileceğin şey. "
            "Şekerleme, çıkartma, ekstra bir oyuncak — bunlar istek "
            "kategorisindedir.",
        ),
        (
            "Karar verirken ezberlik soru",
            "Bir şey almadan önce 'bu ihtiyaç mı, istek mi?' ve "
            "'kumbara hedefimi etkiler mi?' diye sor. Eğer istek "
            "ve hedefini geciktirecekse bir hafta beklemek genelde "
            "iyi karardır.",
        ),
    ),
    examples=(
        "Kantin önünde durdun. Suluk gerekli (ihtiyaç). Yanına çikolata "
        "almak istek. Çikolata 20 ₺, hayalindeki oyuncak 500 ₺. Bir "
        "hafta çikolataya 'hayır' dersen hedefe 5 ₺ daha yaklaşırsın.",
        "Yeni bir kalem kutusu istiyorsun. Eskisi hâlâ çalışıyor mu? "
        "Çalışıyorsa istek; bozulduysa ihtiyaç.",
    ),
    quiz=(
        (
            "Suluk ihtiyaç mı istek mi?",
            "Genelde ihtiyaç, çünkü su içmek zorundayız.",
        ),
        (
            "Bir şey almadan önce hangi iki soruyu sorabilirsin?",
            "1) Bu ihtiyaç mı yoksa istek mi? 2) Kumbara hedefimi geciktirir mi?",
        ),
    ),
)

_LP_PIGGY_BANK_CHILD = _LessonContent(
    goals=(
        "Kumbaranın 'küçük miktarların büyüdüğü yer' olduğunu hissetmek.",
        "Tek seferlik büyük tutar yerine sürekli küçük katkının nasıl işe yaradığını görmek.",
        "Kendine küçük bir kumbara kuralı koymak.",
    ),
    sections=(
        (
            "Kumbara neden işe yarar?",
            "Çünkü küçük tutarları tek bir yerde toplar. Tek tek 5 ₺ "
            "küçük görünür, ama bir araya gelince 'bak ne kadar olmuş' "
            "deyip şaşırırsın.",
        ),
        (
            "Bir kural seç",
            "Mesela: 'her cuma kumbaraya 10 ₺' veya 'bana gelen her "
            "hediyenin yarısı kumbaraya'. Kural küçük olsun ama "
            "düzenli olsun.",
        ),
        (
            "Hayalini görselleştir",
            "Kumbaranı görebileceğin bir yere koy. Üzerine hedefini "
            "yazabilirsin: 'Yaz tatili için' veya 'kitap için'. Her "
            "para attığında hedefe biraz daha yaklaştığını hissedersin.",
        ),
    ),
    examples=(
        "Her hafta 20 ₺ kumbaraya. 10 hafta sonunda 200 ₺ olur. "
        "Yıl sonunda 1.000 ₺'nin üzerinde birikim doğar.",
        "Doğum gününde aldığın 500 ₺'nin 250 ₺'sini kumbaraya, "
        "250 ₺'sini istediğin küçük şeylere ayırırsan iki tarafı "
        "birden mutlu edersin.",
    ),
    quiz=(
        (
            "Tek seferlik büyük para mı, her hafta küçük para mı daha tutarlı bir birikim yapar?",
            "Her hafta küçük para. Düzen alışkanlık yaratır ve hedefe "
            "yavaş ama emin adımlarla yaklaştırır.",
        ),
        (
            "Kumbaraya ne kadar atmalısın?",
            "Kendine seçtiğin küçük bir kural kadar — örneğin haftada "
            "10 ₺. Önemli olan tutar değil, tekrardır.",
        ),
    ),
)


_LESSON_PROFILES_ADULT: dict[str, _LessonContent] = {
    "emergency_fund": _LP_EMERGENCY_FUND_ADULT,
    "interest": _LP_INTEREST_ADULT,
    "compound_interest": _LP_COMPOUND_INTEREST_ADULT,
    "inflation": _LP_INFLATION_ADULT,
    "budget": _LP_BUDGET_ADULT,
    "savings_habit": _LP_SAVINGS_HABIT_ADULT,
    "min_payment": _LP_MIN_PAYMENT_ADULT,
    "subscription": _LP_SUBSCRIPTION_ADULT,
    "diversification": _LP_DIVERSIFICATION_ADULT,
    "money_market_fund": _LP_MONEY_MARKET_FUND_ADULT,
    "income_expense": _LP_INCOME_EXPENSE_ADULT,
    "statement_reading": _LP_STATEMENT_READING_ADULT,
}

_LESSON_PROFILES_CHILD: dict[str, _LessonContent] = {
    "emergency_fund": _LP_EMERGENCY_FUND_CHILD,
    "interest": _LP_INTEREST_CHILD,
    "allowance": _LP_ALLOWANCE_CHILD,
    "need_want": _LP_NEED_WANT_CHILD,
    "piggy_bank": _LP_PIGGY_BANK_CHILD,
}


def _match_lesson_kind(topic: str) -> str | None:
    """Map a free-form Turkish topic to a canonical lesson profile kind."""
    normalized = topic.casefold()
    # Order matters: more specific patterns first.
    if "asgari" in normalized and ("kredi" in normalized or "kart" in normalized):
        return "min_payment"
    if re.search(r"\b(bile[şs]ik|compound)\b", normalized) and "faiz" in normalized:
        return "compound_interest"
    if "acil" in normalized and ("fon" in normalized or "durum" in normalized):
        return "emergency_fund"
    if "enflasyon" in normalized:
        return "inflation"
    if "bütçe" in normalized or "butce" in normalized:
        return "budget"
    if "abonelik" in normalized or "tekrarlayan" in normalized:
        return "subscription"
    if re.search(r"çe[şs]itlendirme|çe[şs]itlendir", normalized):
        return "diversification"
    if "para piyasası" in normalized or "para piyasasi" in normalized:
        return "money_market_fund"
    if re.search(r"\bppf\b", normalized):
        return "money_market_fund"
    if "ekstre" in normalized:
        return "statement_reading"
    if "tasarruf" in normalized or "biriktir" in normalized:
        return "savings_habit"
    if "ihtiyaç" in normalized and "istek" in normalized:
        return "need_want"
    if "kumbara" in normalized:
        return "piggy_bank"
    if "harçlık" in normalized or "harclik" in normalized or "haftalik" in normalized:
        return "allowance"
    if "faiz" in normalized:
        return "interest"
    if "gelir" in normalized and "gider" in normalized:
        return "income_expense"
    return None


def _resolve_lesson_content(topic: str, level: str) -> _LessonContent | None:
    kind = _match_lesson_kind(topic)
    if kind is None:
        return None
    if level == "child":
        return _LESSON_PROFILES_CHILD.get(kind) or _LESSON_PROFILES_ADULT.get(kind)
    return _LESSON_PROFILES_ADULT.get(kind)


def _distribute_lesson_minutes(total: int, count: int) -> list[int]:
    """Split `total` minutes across `count` sections as evenly as possible."""
    if count <= 0:
        return []
    base = max(1, total // count)
    remainder = max(0, total - base * count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def _custom_lesson_goals(topic: str, level: str) -> list[str]:
    content = _resolve_lesson_content(topic, level)
    if content is not None:
        return list(content.goals)
    if level == "child":
        return [
            f"{topic} konusunu günlük hayattan somut bir örnekle anlamak.",
            "Bu konunun harçlık, kumbara veya doğum günü hediyesi gibi "
            "küçük kararlara nasıl dokunduğunu görmek.",
            "Ders sonunda kendi cümlesiyle bir küçük para alışkanlığı seçmek.",
        ]
    return [
        f"{topic} kavramını gelir, gider, risk ve zaman penceresinden "
        "ayrı ayrı değerlendirebilmek.",
        "Bu konunun aile bütçesinin hangi zarfına veya satırına dokunduğunu "
        "somut bir kalemle örneklemek.",
        "Önümüzdeki 30 gün içinde izlenebilir tek bir takip adımı seçmek.",
    ]


def _custom_lesson_sections(
    topic: str, level: str, duration_minutes: int
) -> list[dict[str, object]]:
    content = _resolve_lesson_content(topic, level)
    if content is not None:
        minutes_per_section = _distribute_lesson_minutes(duration_minutes, len(content.sections))
        return [
            {"title": title, "minutes": minutes_per_section[index], "content": body}
            for index, (title, body) in enumerate(content.sections)
        ]
    if level == "child":
        sections = (
            (
                "Konu nedir?",
                f"{topic}, para ile ilgili bir kararı daha anlaşılır hale "
                "getiren bir fikir gibi anlatılır. Çocuk için bu konu harçlık, "
                "kumbara ve kantin alışverişi üzerinden somutlaşır: elindeki "
                "paranın bir kısmı bugünkü istekler için, bir kısmı daha sonra "
                "almak istediğin şeyler için ayrılır. Böylece konu ezberlenen "
                "bir kelime olmaktan çıkar, günlük seçimlere yardım eden küçük "
                "bir pusula olur.",
            ),
            (
                "Birlikte düşün",
                "Küçük bir hikaye kur: oyuncak, dondurma veya doğum günü "
                "hediyesi almak istiyorsun. Bu derste konu, karar vermeden önce "
                "'hemen mi harcasam, biraz beklesem mi, kumbaramı etkiler mi?' "
                "sorularını sordurur. Eğer cevap 'beklersem daha büyük hedefime "
                "yaklaşırım' ise harcamayı ertelemek anlamlı olabilir; cevap "
                "'bu okul için gerekli' ise ihtiyaç olarak öne geçebilir.",
            ),
            (
                "Mini söz",
                "Dersin sonunda bir haftalık küçük bir söz seçilir. Örneğin "
                "harçlık gelince önce 10 ₺ ayırmak, kantinde istediğin bir şeyi "
                "almadan önce bir gün beklemek veya kumbaraya hedef etiketi "
                "yapıştırmak. Amaç büyük ve zor bir söz vermek değil; kolay "
                "tekrarlanabilen küçük bir davranışı para alışkanlığına çevirmektir.",
            ),
        )
    else:
        sections = (
            (
                "Kavramı sadeleştir",
                f"{topic}, aile bütçesinde tek başına ezberlenecek bir başlık "
                "gibi değil, para kararlarını netleştiren bir araç gibi ele "
                "alınır. Önce bu kavramın gelir, gider, risk veya zaman "
                "başlıklarından hangisine dokunduğu anlatılır. Böylece kullanıcı "
                "'bu bilgi benim bütçemde hangi kararı kolaylaştırıyor?' sorusuna "
                "somut cevap bulur.",
            ),
            (
                "Bütçeye çevir",
                "Aylık 15.000–25.000 ₺ gider bandındaki bir aileyi düşün. "
                f"{topic} bir karara dönüştüğünde hangi kalem değişir, hangi "
                "zarf etkilenir ve tahmini aylık etki kaç ₺ olur? Bu bölümde "
                "kavram gerçek hane bütçesine indirilir: market, fatura, ulaşım, "
                "abonelik veya birikim gibi tanıdık satırlardan biriyle bağ kurulur. "
                "Amaç soyut bilgiyi 'bu ay neyi takip edeceğim?' sorusuna çevirmektir.",
            ),
            (
                "Bugünden uygulanacak adım",
                "Dersin sonunda önümüzdeki 30 günde izlenebilir tek bir takip "
                "adımı belirlenir: "
                "ilgili zarfta bir limit güncellemek, tekrarlayan bir ödemeyi "
                "gözden geçirmek veya birikim katkısını ayarlamak. Böylece "
                "ders yalnızca bilgi olarak kalmaz; kullanıcının takvimine, "
                "bütçe ekranına veya aile içi para konuşmasına girebilecek küçük "
                "bir davranışa dönüşür.",
            ),
        )
    minutes_per_section = _distribute_lesson_minutes(duration_minutes, len(sections))
    return [
        {"title": title, "minutes": minutes_per_section[index], "content": body}
        for index, (title, body) in enumerate(sections)
    ]


def _custom_lesson_examples(topic: str, level: str) -> list[str]:
    content = _resolve_lesson_content(topic, level)
    if content is not None:
        return list(content.examples)
    if level == "child":
        return [
            f"Diyelim ki harçlığın 100 ₺. {topic} konusu bir karar gerektirse "
            "(örneğin oyuncak almak), kumbara hedefini nasıl etkiler?",
            "Kantin alışverişinden önce 'bu ihtiyaç mı, istek mi?' diye sor. "
            "Cevaba göre küçük bir karar al.",
        ]
    return [
        f"Aylık 18.000 ₺ giderli bir aile {topic} kalemini %5 ayarlasa, "
        "aylık etki yaklaşık 900 ₺, yıllık etki yaklaşık 10.800 ₺ olur.",
        f"Geçen ay kayıtlarına bak: {topic} ile ilişkilendirebileceğin bir "
        "kalem var mı? Bu kalem aylık bütçenin yaklaşık yüzde kaçını "
        "oluşturuyor?",
    ]


def _custom_lesson_quiz(topic: str, level: str) -> list[dict[str, object]]:
    content = _resolve_lesson_content(topic, level)
    if content is not None:
        return [{"question": question, "answer": answer} for question, answer in content.quiz]
    if level == "child":
        return [
            {
                "question": f"{topic} ile ilgili karar verirken ilk neye bakarsın?",
                "answer": "Gerçekten gerekli mi, kumbaramdaki hedefe ne yapar "
                "ve bir hafta bekleyebilir miyim diye düşünürüm.",
            },
            {
                "question": "Küçük birikim neden işe yarar?",
                "answer": "Çünkü küçük tutarlar düzenli olunca zamanla büyür "
                "ve hayalindeki şeye yaklaştırır.",
            },
        ]
    return [
        {
            "question": f"{topic} aile bütçesinde hangi dört pencereden değerlendirilir?",
            "answer": "Gelir, gider, risk ve zaman. Her karar bu dört "
            "pencereden en az birine dokunur.",
        },
        {
            "question": "Bu ders belirli bir ürün veya yatırım tavsiyesi verebilir mi?",
            "answer": "Hayır. Eğitim amaçlıdır; belirli ürün, fon, hisse, "
            "kripto veya getiri tavsiyesi yapılmaz.",
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
    safe_level = _normalize_lesson_level(level, current_user)
    matched_content = _resolve_lesson_content(normalized_topic, safe_level)
    minimum_duration = len(matched_content.sections) if matched_content is not None else 3
    safe_duration = max(minimum_duration, min(duration_minutes, 12))
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
    """Kullanıcının abonelik ve tekrarlayan gelir/gider özetini döner."""
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
