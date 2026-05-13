"""Agent tool implementations backed by scoped database queries."""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
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
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.services.image_gen import IllustrationService, IllustrationUnavailableError
from app.services.ocr import ReceiptOcrError, ReceiptOcrService, ReceiptOcrUnavailableError
from app.utils.date_format import format_tr_date
from app.utils.recurrence import monthly_equivalent, recurrence_label
from app.utils.tl_format import format_tl

MONEY_QUANT = Decimal("0.01")
MAX_SPENDING_DAYS = 365
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


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _decimal_text(value: Decimal) -> str:
    return f"{_money(value):.2f}"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalized_days(days: int) -> int:
    return max(1, min(days, MAX_SPENDING_DAYS))


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
    user_ids = visible_user_ids(current_user)
    categories = visible_categories(db, current_user)
    category_names = {item.id: item.name for item in categories}
    category_filter = category.casefold() if category else None

    transactions = list(
        db.execute(
            select(Transaction)
            .where(
                Transaction.user_id.in_(user_ids),
                Transaction.occurred_at >= period_start,
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
    latest_transaction: datetime | None = None

    for transaction in transactions:
        category_name = (
            category_names.get(transaction.category_id, "Kategorisiz")
            if transaction.category_id is not None
            else "Kategorisiz"
        )
        if category_filter is not None and category_filter not in category_name.casefold():
            continue
        amount = Decimal(transaction.amount)
        total += amount
        included += 1
        category_totals[category_name] = category_totals.get(category_name, Decimal("0")) + amount
        occurred_at = _aware_utc(transaction.occurred_at)
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

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_start_formatted": format_tr_date(period_start),
        "period_end_formatted": format_tr_date(period_end),
        "days": safe_days,
        "category": category,
        "transaction_count": included,
        "total_amount": _decimal_text(total),
        "total_amount_formatted": format_tl(total),
        "latest_transaction_date": latest_transaction.isoformat() if latest_transaction else None,
        "latest_transaction_date_formatted": (
            format_tr_date(latest_transaction) if latest_transaction else None
        ),
        "category_totals": rows,
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


def build_spending_chart(
    db: Session,
    current_user: User,
    *,
    days: int = 30,
    chart_type: str = "bar",
    now: datetime | None = None,
) -> dict[str, object]:
    """Return a chart specification of the user's category spending.

    The chart payload is rendered inline by the frontend when it sees a `chart`
    key on a tool_result event. Same `visible_user_ids` scope as get_spending.
    """
    if chart_type not in {"bar", "pie"}:
        chart_type = "bar"
    summary = build_spending_summary(db, current_user, days=days, now=now)
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
    days: int = 30,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Kullanıcının harcama özetini döner. `user_id` sistem durumundan gelir."""
    with SessionLocal() as db:
        return build_spending_summary(
            db,
            _load_current_user(db, user_id),
            category=category,
            days=days,
        )


@tool("get_subscriptions")
def get_subscriptions_tool(
    only_active: bool = True,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Kullanıcının abonelik ve tekrarlayan ödeme özetini döner."""
    with SessionLocal() as db:
        return build_subscriptions_summary(
            db,
            _load_current_user(db, user_id),
            only_active=only_active,
        )


@tool("get_user_memory")
def get_user_memory_tool(
    key: str | None = None,
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Agent'in mevcut kullanıcı için hatırladığı bilgileri döner."""
    with SessionLocal() as db:
        return build_user_memory(db, _load_current_user(db, user_id), key=key)


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
    days: int = 30,
    chart_type: str = "bar",
    user_id: Annotated[str, InjectedState("user_id")] = "",
) -> dict[str, object]:
    """Harcama özetinden kategori bazında grafik üretir; chat'te inline çizilir.

    `chart_type` 'bar' veya 'pie' olabilir. `days` 1-365 aralığında olmalı.
    Tüm veri agent state'inden gelen user_id kapsamı içindedir.
    """
    with SessionLocal() as db:
        return build_spending_chart(
            db,
            _load_current_user(db, user_id),
            days=days,
            chart_type=chart_type,
        )


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
    analyze_receipt_tool,
    explain_concept_tool,
    simulate_scenario_tool,
    get_user_memory_tool,
    visualize_spending_tool,
    illustrate_concept_tool,
]
