"""Small streaming runner that turns scoped tool results into SSE events."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Any, TypedDict
from uuid import UUID

from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agent.graph import build_agent_graph_from_settings
from app.agent.tools import (
    build_accumulation_goal_creation,
    build_concept_illustration,
    build_receipt_candidate,
    build_saving_goal_creation,
    build_saving_goal_progress,
    build_spending_chart,
    build_spending_summary,
    build_subscriptions_summary,
    build_user_memory,
    explain_finance_concept,
    infer_category_from_text,
    simulate_finance_scenario,
)
from app.config import Settings, get_settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ChatStreamRequest
from app.services.envelopes import resolve_envelope_category
from app.services.smart_plans import build_smart_saving_plan


class ChatStreamEvent(TypedDict, total=False):
    type: str
    conversation_id: str
    role: str
    content: str
    tool_name: str
    input: dict[str, object]
    result: dict[str, object]
    image_url: str
    alt_text: str


SUBSCRIPTION_HINTS = ("abonelik", "abonelikler", "tekrarlayan", "subscription")
CONCEPT_HINTS = (
    "nedir",
    "faiz",
    "enflasyon",
    "bütçe",
    "butce",
    "tasarruf",
    "biriktir",
    "harçlık",
    "harclik",
    "fon",
    "para piyasası",
    "para piyasasi",
)
SCENARIO_HINTS = ("asgari", "kredi kart", "senaryo", "ödesem", "odesem")
VISUALIZE_HINTS = ("grafik", "grafiğ", "chart", "görselle", "gorselle", "pasta", "bar grafik")
MONTHLY_VISUALIZE_HINTS = (
    "ay ay",
    "her ay",
    "aylık trend",
    "aylik trend",
    "aylık değiş",
    "aylik degis",
    "nasıl değişti",
    "nasil degisti",
    "month by month",
)
MEMORY_HINTS = ("hafıza", "hafiza", "hatırl", "hatirl", "memory")
SAVING_GOAL_CREATE_HINTS = (
    "azalt",
    "düşür",
    "dusur",
    "tasarruf hedefi oluştur",
    "tasarruf hedefi olustur",
    "hedef koy",
)
ACCUMULATION_GOAL_CREATE_HINTS = (
    "birikim hedefi oluştur",
    "birikim hedefi olustur",
    "birikim hedefi koy",
    "biriktirme hedefi",
    "para biriktirmek istiyorum",
)
SAVING_GOAL_PROGRESS_HINTS = ("hedefimde", "hedefim", "tasarruf hedef", "ilerleme", "durum")
SMART_PLAN_HINTS = (
    "tatil",
    "giderlerimi kısm",
    "giderlerimi kism",
    "nereden kısm",
    "nereden kism",
    "para biriktiremiyorum",
    "birikim plan",
    "akıllı hedef",
    "akilli hedef",
)
ENVELOPE_BUDGET_HINTS = (
    "zarf",
    "bütçe",
    "butce",
    "kald",
    "kalan",
    "harcad",
    "ne kadar",
)
ILLUSTRATION_HINTS = (
    "görsel",
    "gorsel",
    "resim",
    "illüstrasyon",
    "illustrasyon",
    "görselle",
    "gorselle",
    "çiz",
    "ciz",
)
INVESTMENT_TERMS = (
    "hisse",
    "borsa",
    "kripto",
    "bitcoin",
    "ethereum",
    "coin",
    "fon",
    "altın",
    "altin",
    "döviz",
    "doviz",
    "yatırım",
    "yatirim",
)
INVESTMENT_ADVICE_PATTERNS = (
    r"\b(alayım|alayim|almalı|almali|alınır|alinir)\b",
    r"\b(satayım|satayim|satmalı|satmali|satılır|satilir)\b",
    r"\bhangi\b",
    r"\bneye yat[ıi]r",
    r"\bportf[öo]y\b",
    r"\b(öner|oner|önerir|onerir)\b",
    r"\btavsiye (?:et|eder|edersin|edilir|ver|verir|istiyorum)\b",
    r"\byat[ıi]r[ıi]m tavsiyesi (?:ver|verir|istiyorum|laz[ıi]m|gerek)\b",
)
NEGATED_SHORT_TRADE_HINTS = ("al/sat", "al-sat", "al sat tavsiyesi verme")
MAX_CONTEXT_MESSAGES = 20


def _get_or_create_conversation(
    db: Session,
    current_user: User,
    conversation_id: UUID | None,
) -> Conversation:
    if conversation_id is None:
        conversation = Conversation(user_id=current_user.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    existing = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        ),
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sohbet bulunamadı.",
        )
    return existing


def _persist_message(
    db: Session,
    conversation: Conversation,
    *,
    role: str,
    content: str,
    tool_name: str | None = None,
    tool_calls: dict[str, object] | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        tool_name=tool_name,
        tool_calls=tool_calls,
    )
    db.add(message)
    db.commit()
    return message


def _sanitize_payload(value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            if key in {"image_base64", "receipt_image_base64", "raw_text"}:
                sanitized[key] = "[redacted]"
            elif key == "raw_ocr_data" and isinstance(item, dict):
                sanitized[key] = {
                    "provider": item.get("provider"),
                    "source_filename": item.get("source_filename"),
                }
            else:
                sanitized[key] = _sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    return value


def _json_payload(value: object) -> dict[str, object]:
    sanitized = _sanitize_payload(value)
    if isinstance(sanitized, dict):
        return sanitized
    return {"value": sanitized}


def _chunks(text: str) -> Iterator[str]:
    words = text.split(" ")
    bucket: list[str] = []
    for word in words:
        bucket.append(word)
        if len(bucket) == 7:
            yield " ".join(bucket) + " "
            bucket = []
    if bucket:
        yield " ".join(bucket)


def _wants_subscriptions(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in SUBSCRIPTION_HINTS)


def _wants_concept(message: str) -> bool:
    if _wants_envelope_budget(message):
        return False
    if _wants_smart_saving_plan(message):
        return False
    normalized = message.casefold()
    return any(hint in normalized for hint in CONCEPT_HINTS)


def _wants_scenario(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in SCENARIO_HINTS)


def _wants_visualization(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in (*VISUALIZE_HINTS, *MONTHLY_VISUALIZE_HINTS))


def _wants_monthly_visualization(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in MONTHLY_VISUALIZE_HINTS)


def _wants_memory(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in MEMORY_HINTS)


def _wants_saving_goal_creation(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in SAVING_GOAL_CREATE_HINTS)


def _wants_accumulation_goal_creation(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in ACCUMULATION_GOAL_CREATE_HINTS)


def _wants_saving_goal_progress(message: str) -> bool:
    normalized = message.casefold()
    return "hedef" in normalized and any(hint in normalized for hint in SAVING_GOAL_PROGRESS_HINTS)


def _wants_smart_saving_plan(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in SMART_PLAN_HINTS)


def _wants_illustration(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in ILLUSTRATION_HINTS)


def _wants_investment_advice(message: str) -> bool:
    normalized = message.casefold()
    has_investment_term = any(term in normalized for term in INVESTMENT_TERMS)
    if not has_investment_term:
        return False

    has_advice_pattern = any(
        re.search(pattern, normalized) for pattern in INVESTMENT_ADVICE_PATTERNS
    )
    has_short_trade_action = bool(re.search(r"\b(al|sat)\b", normalized)) and not any(
        hint in normalized for hint in NEGATED_SHORT_TRADE_HINTS
    )
    return has_advice_pattern or has_short_trade_action


def _wants_envelope_budget(message: str) -> bool:
    normalized = message.casefold()
    return resolve_envelope_category(message) is not None and any(
        hint in normalized for hint in ENVELOPE_BUDGET_HINTS
    )


def _int_result(result: dict[str, object], key: str) -> int:
    value = result[key]
    if isinstance(value, int):
        return value
    return int(str(value))


def _decimal_result(result: dict[str, object], key: str) -> Decimal | None:
    value = result.get(key)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


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
    return max(amounts) if amounts else None


def _target_months_from_message(message: str) -> int:
    normalized = message.casefold()
    month_match = re.search(r"(\d{1,3})\s*(?:ay|ayda|aylık|aylik)", normalized)
    if month_match:
        return max(1, min(int(month_match.group(1)), 120))
    year_match = re.search(r"(\d{1,2})\s*(?:yıl|yil|senede|sene)", normalized)
    if year_match:
        return max(1, min(int(year_match.group(1)) * 12, 120))
    return 12


def _accumulation_title_from_message(message: str) -> str:
    normalized = message.casefold()
    if "tatil" in normalized:
        return "Tatil birikimi"
    if "okul" in normalized or "eğitim" in normalized or "egitim" in normalized:
        return "Eğitim birikimi"
    if "telefon" in normalized:
        return "Telefon birikimi"
    if "acil" in normalized:
        return "Acil durum birikimi"
    return "Birikim hedefi"


def _spending_answer(result: dict[str, object]) -> str:
    category = result.get("category")
    category_text = f"{category} kategorisinde" if category else "tüm kategorilerde"
    total = str(result["total_amount_formatted"])
    count = _int_result(result, "transaction_count")
    days = _int_result(result, "days")
    envelope = result.get("budget_envelope")
    savings = result.get("savings_envelope")
    if isinstance(envelope, dict):
        label = str(envelope.get("label") or "Bu zarf")
        envelope_name = label.replace(" zarfı", "").casefold()
        remaining = str(envelope.get("remaining_formatted") or "0,00 ₺")
        remaining_value = _decimal_result(envelope, "remaining")
        safe_daily = str(envelope.get("safe_daily_amount_formatted") or "0,00 ₺")
        days_left = envelope.get("days_left_in_month")
        if envelope.get("is_savings_goal"):
            if remaining_value is not None and remaining_value <= 0:
                return f"{label} bu ay tamamlanmış görünüyor."
            answer = f"{label}nda bu ay {remaining} daha ayırman gerekiyor."
            if isinstance(days_left, int) and days_left > 0:
                answer = (
                    f"{answer} Ay sonuna {days_left} gün var; günlük hedef yaklaşık {safe_daily}."
                )
            return answer
        if remaining_value is not None and remaining_value < 0:
            answer = f"{label} bu ay {format_amount_text(str(abs(remaining_value)))} aşıldı."
        else:
            answer = f"{label}nda bu ay {remaining} kaldı."
            if isinstance(days_left, int) and days_left > 0:
                answer = (
                    f"{answer} Ay sonuna {days_left} gün var; günlük güvenli {envelope_name} "
                    f"harcaman yaklaşık {safe_daily}."
                )
        if isinstance(savings, dict) and not envelope.get("is_savings_goal"):
            savings_remaining = _decimal_result(savings, "remaining")
            if savings_remaining is not None and savings_remaining <= 0:
                answer = f"{answer} Birikim hedefi bu ay tamamlanmış görünüyor."
            else:
                answer = (
                    f"{answer} Birikim hedefi için {savings.get('remaining_formatted', '0,00 ₺')} "
                    "daha ayırman gerekiyor."
                )
        return answer
    if count == 0:
        return (
            f"Son {days} günde {category_text} kayıtlı gider bulamadım. "
            "İlk işlemini eklediğinde buradan gerçek veriye göre yanıt verebilirim."
        )
    return (
        f"Son {days} günde {category_text} toplam harcaman {total}. "
        f"Bu tutar {count} işlemden hesaplandı."
    )


def _subscription_answer(result: dict[str, object]) -> str:
    count = _int_result(result, "count")
    total = str(result["monthly_total_formatted"])
    if count == 0:
        return (
            "Aktif abonelik veya tekrarlayan ödeme kaydı bulamadım. "
            "Eklediğinde aylık etkisini burada birlikte takip edebiliriz."
        )
    return f"Aktif tekrarlayan ödemelerin aylık etkisi {total}. Toplam {count} kayıt var."


def _receipt_answer(result: dict[str, object]) -> str:
    if "error" in result:
        return str(result["error"])
    merchant = result.get("merchant") or "Fiş"
    amount = result.get("amount")
    category = result.get("category_name") or "Kategorisiz"
    items = result.get("items")
    item_count = len(items) if isinstance(items, list) else 0
    amount_text = format_amount_text(str(amount)) if amount is not None else "tutar okunamadı"
    return (
        f"{merchant} fişini okudum: toplam {amount_text}, kategori önerisi {category}. "
        f"{item_count} satır kalemi bulundu. İşleme kaydetmeden önce Fişler ekranındaki onay "
        "masasından kontrol edebilirsin."
    )


def format_amount_text(value: str) -> str:
    try:
        numeric = Decimal(value.replace(",", "."))
        whole, fraction = f"{numeric:.2f}".split(".")
        grouped = f"{int(whole):,}".replace(",", ".")
        return f"{grouped},{fraction} ₺"
    except (InvalidOperation, ValueError):
        return value


def _concept_answer(result: dict[str, object]) -> str:
    explanation = result.get("explanation")
    return str(explanation) if explanation else "Bu kavramı açıklayamadım, tekrar dener misin?"


def _scenario_answer(result: dict[str, object]) -> str:
    summary = result.get("summary")
    return str(summary) if summary else "Bu senaryo için daha fazla bilgiye ihtiyacım var."


def _investment_refusal_answer() -> str:
    return (
        "Yatırım tavsiyesi veremem; hangi hisse, fon, kripto, altın veya dövizin "
        "alınıp satılacağını söyleyemem. İstersen risk, vade, çeşitlendirme ve bütçeye "
        "etki gibi kavramları genel ve eğitici şekilde açıklayabilirim."
    )


def _visualization_answer(result: dict[str, object]) -> str:
    total = str(result.get("total_amount_formatted", "0,00 ₺"))
    count = _int_result(result, "transaction_count") if "transaction_count" in result else 0
    days = _int_result(result, "days") if "days" in result else 30
    chart = result.get("chart")
    chart_type = chart.get("type") if isinstance(chart, dict) else None
    if chart_type == "monthly":
        months = _int_result(result, "month_count") if "month_count" in result else 0
        period_text = f"Son {months} ayda" if months > 0 else f"Son {days} günde"
        if count == 0:
            return (
                f"{period_text} aylık trend için gösterecek gider bulamadım. "
                "İlgili işlem kayıtları oluştuğunda değişimi ay ay çizebilirim."
            )
        return (
            f"{period_text} aylık değişimi çizdim, toplam {total}, {count} işlem. "
            "Grafiği hemen üstünde görebilirsin."
        )
    if count == 0:
        return (
            f"Son {days} günde gösterecek bir gider bulamadım, bu yüzden grafik şu an boş. "
            "İlk işlemi eklediğinde kategori dağılımını çizebilirim."
        )
    return (
        f"Son {days} günün kategori dağılımını çizdim, toplam {total}, {count} işlem. "
        "Grafiği hemen üstünde görebilirsin."
    )


def _memory_answer(result: dict[str, object]) -> str:
    count = _int_result(result, "count") if "count" in result else 0
    entries = result.get("entries")
    if count == 0 or not isinstance(entries, list):
        return "Hafızamda bu profil için kayıtlı bir bilgi bulamadım."
    labels: list[str] = []
    for entry in entries[:5]:
        if isinstance(entry, dict) and isinstance(entry.get("key"), str):
            labels.append(str(entry["key"]))
    if labels:
        return f"Hafızamda bu profil için {count} kayıt var: {', '.join(labels)}."
    return f"Hafızamda bu profil için {count} kayıt var."


def _saving_goal_answer(result: dict[str, object], *, created: bool) -> str:
    if result.get("goal_type") == "accumulation":
        return _accumulation_goal_answer(result, created=created)
    if "error" in result:
        category = result.get("category")
        suffix = f" ({category})" if category else ""
        return f"Tasarruf hedefi için veriyi netleştiremedim{suffix}: {result['error']}"
    category_name = str(result.get("category_name", "Bu kategori"))
    baseline = str(result.get("baseline_amount_formatted", "0,00 ₺"))
    target = str(result.get("target_spending_amount_formatted", "0,00 ₺"))
    saving = str(result.get("target_saving_amount_formatted", "0,00 ₺"))
    actual = str(result.get("actual_spending_formatted", "0,00 ₺"))
    remaining = str(result.get("remaining_limit_formatted", "0,00 ₺"))
    tactics = result.get("tactics")
    first_tactic = ""
    if isinstance(tactics, list) and tactics:
        first_tactic = f" İlk taktik: {tactics[0]}"
    if created:
        return (
            f"{category_name} için tasarruf hedefini oluşturdum. Son 30 gün bazın {baseline}; "
            f"bu ay {target} altında kalırsan yaklaşık {saving} tasarruf edebilirsin."
            f"{first_tactic}"
        )
    status_label = str(result.get("status_label", "on_track"))
    status_text = {
        "on_track": "iyi gidiyor",
        "at_risk": "riskte",
        "over_limit": "limit aşılmış görünüyor",
        "completed": "tamamlanmış görünüyor",
    }.get(status_label, "takipte")
    return (
        f"{category_name} tasarruf hedefin {status_text}. Hedef limitin {target}; "
        f"şu ana kadar {actual} harcadın. Kalan limit {remaining}."
        f"{first_tactic}"
    )


def _accumulation_goal_answer(result: dict[str, object], *, created: bool) -> str:
    if "error" in result:
        return f"Birikim hedefi için veriyi netleştiremedim: {result['error']}"
    title = str(result.get("title") or "Birikim hedefi")
    target = str(result.get("target_amount_formatted") or "0,00 ₺")
    current = str(result.get("current_amount_formatted") or "0,00 ₺")
    remaining = str(result.get("remaining_amount_formatted") or "0,00 ₺")
    monthly = str(result.get("monthly_contribution_formatted") or "0,00 ₺")
    if created:
        return (
            f"{title} oluşturdum. Hedef tutar {target}; şu an {current} var. "
            f"Kalan {remaining}. Aylık yaklaşık {monthly} ayırarak takip edebilirsin."
        )
    return f"{title} için kalan tutar {remaining}; aylık takip tutarı yaklaşık {monthly}."


def _smart_saving_plan_answer(result: dict[str, object]) -> str:
    goals = result.get("goals")
    accumulation = result.get("accumulation_goal")
    if not isinstance(goals, list) or not goals:
        if isinstance(accumulation, dict):
            title = str(accumulation.get("title") or "Birikim hedefi")
            target_amount = str(accumulation.get("target_amount_formatted") or "0,00 ₺")
            monthly = str(accumulation.get("monthly_contribution_formatted") or "0,00 ₺")
            return (
                f"{title} için {target_amount} hedefi açtım; aylık yaklaşık {monthly} gerekir. "
                "Son 30 günde kategori bazlı azaltma hedefi önermek için yeterli gider verisi bulamadım."
            )
        return (
            "Akıllı hedef planı için son 30 günde yeterli kategori harcaması bulamadım. "
            "Birkaç işlem eklediğinde nereden kısabileceğini birlikte çıkarabilirim."
        )
    target = str(result.get("target_label") or "hedef")
    expense = str(result.get("total_expense_formatted") or "0,00 ₺")
    saving = str(result.get("expected_monthly_saving_formatted") or "0,00 ₺")
    parts = [
        f"{target} hedefin için son 30 gün verine baktım; toplam gider {expense}.",
        f"İlk aşamada yaklaşık {saving} aylık tasarruf potansiyeli olan hedefler oluşturdum.",
    ]
    goal_lines: list[str] = []
    for item in goals[:2]:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category_name") or "Kategori")
        target_spending = str(item.get("target_spending_amount_formatted") or "0,00 ₺")
        target_saving = str(item.get("target_saving_amount_formatted") or "0,00 ₺")
        goal_lines.append(
            f"{category}: bu ay {target_spending} altında kal, yaklaşık {target_saving} kazan."
        )
    if goal_lines:
        parts.append(" ".join(goal_lines))
    if isinstance(accumulation, dict):
        title = str(accumulation.get("title") or "Birikim hedefi")
        target_amount = str(accumulation.get("target_amount_formatted") or "0,00 ₺")
        monthly = str(accumulation.get("monthly_contribution_formatted") or "0,00 ₺")
        parts.append(
            f"{title} için {target_amount} hedefi açtım; aylık yaklaşık {monthly} gerekir."
        )
    subscription_note = result.get("subscription_note")
    if isinstance(subscription_note, str):
        monthly = str(result.get("subscription_monthly_total_formatted") or "0,00 ₺")
        parts.append(f"Aboneliklerin aylık etkisi {monthly}; {subscription_note}")
    if not isinstance(accumulation, dict):
        parts.append("Birikim tarafını aylık Birikim zarfı ile takip edebilirsin.")
    return " ".join(parts)


def _image_event_from_result(
    *,
    conversation_id: str,
    result: dict[str, object],
) -> ChatStreamEvent | None:
    image_url = result.get("image_url")
    if not isinstance(image_url, str) or not image_url:
        return None
    alt_text = result.get("alt_text")
    return {
        "type": "image",
        "conversation_id": conversation_id,
        "image_url": image_url,
        "alt_text": alt_text if isinstance(alt_text, str) else "Finansal kavram görseli",
    }


def _receipt_context(result: dict[str, object]) -> str:
    if "error" in result:
        return f"Fiş OCR hatası: {result['error']}"
    merchant = result.get("merchant")
    amount = result.get("amount")
    category = result.get("category_name")
    return (
        "Fiş OCR sonucu: "
        f"satıcı={merchant}, tutar={amount}, kategori={category}, "
        "kullanıcı onayı olmadan işlem yazılmadı."
    )


def _live_agent_available(settings: Settings) -> bool:
    if settings.llm_provider == "openrouter":
        return bool(settings.openrouter_api_key)
    return bool(settings.gemini_api_key)


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return str(content)


def _tool_result_payload(message: ToolMessage) -> dict[str, object]:
    try:
        parsed: object = json.loads(_message_text(message.content))
    except json.JSONDecodeError:
        parsed = {"content": message.content}
    return _json_payload(parsed)


def _tool_call_name(call: dict[str, Any]) -> str:
    value = call.get("name")
    return value if isinstance(value, str) else "tool"


def _tool_call_args(call: dict[str, Any]) -> dict[str, object]:
    args = call.get("args")
    return _json_payload(args if isinstance(args, dict) else {})


def _graph_context_messages(
    db: Session,
    conversation: Conversation,
    *,
    current_user_message: Message,
    current_user_content: str,
) -> list[BaseMessage]:
    rows = list(
        db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.role.in_(("user", "assistant")),
            )
            .order_by(desc(Message.created_at))
            .limit(MAX_CONTEXT_MESSAGES),
        )
        .scalars()
        .all(),
    )
    messages: list[BaseMessage] = []
    for row in reversed(rows):
        is_current_user_message = row is current_user_message or row.id == current_user_message.id
        content = current_user_content if is_current_user_message else row.content
        if row.role == "user":
            messages.append(HumanMessage(content=content))
        elif row.role == "assistant":
            messages.append(AIMessage(content=content))
    if not messages:
        messages.append(HumanMessage(content=current_user_content))
    return messages


def _stream_live_graph(
    db: Session,
    current_user: User,
    payload: ChatStreamRequest,
    conversation: Conversation,
    *,
    current_user_message: Message,
    receipt_context: str | None = None,
    settings: Settings | None = None,
) -> Iterator[ChatStreamEvent]:
    graph = build_agent_graph_from_settings(settings)
    user_content = (
        payload.message if receipt_context is None else f"{payload.message}\n\n{receipt_context}"
    )
    graph_messages = _graph_context_messages(
        db,
        conversation,
        current_user_message=current_user_message,
        current_user_content=user_content,
    )
    final_answer = ""
    for update in graph.stream(
        {
            "messages": graph_messages,
            "user_id": str(current_user.id),
            "user_role": current_user.role,
            "finance_level": current_user.finance_level,
        },
        stream_mode="updates",
    ):
        if not isinstance(update, dict):
            continue
        messages: list[BaseMessage] = []
        for node_value in update.values():
            if isinstance(node_value, dict) and isinstance(node_value.get("messages"), list):
                messages.extend(node_value["messages"])
        for message in messages:
            if isinstance(message, AIMessage):
                tool_calls = getattr(message, "tool_calls", None) or []
                if tool_calls:
                    for call in tool_calls:
                        tool_name = _tool_call_name(call)
                        tool_input = _tool_call_args(call)
                        yield {
                            "type": "tool_call",
                            "conversation_id": str(conversation.id),
                            "tool_name": tool_name,
                            "input": tool_input,
                        }
                else:
                    content = _message_text(message.content)
                    final_answer = content
                    for chunk in _chunks(content):
                        yield {
                            "type": "delta",
                            "conversation_id": str(conversation.id),
                            "content": chunk,
                        }
            elif isinstance(message, ToolMessage):
                result = _tool_result_payload(message)
                _persist_message(
                    db,
                    conversation,
                    role="tool",
                    content="Araç sonucu alındı.",
                    tool_name=message.name or "tool",
                    tool_calls={"result": result},
                )
                yield {
                    "type": "tool_result",
                    "conversation_id": str(conversation.id),
                    "tool_name": message.name or "tool",
                    "result": result,
                }
                image_event = _image_event_from_result(
                    conversation_id=str(conversation.id),
                    result=result,
                )
                if image_event is not None:
                    yield image_event
    if final_answer:
        _persist_message(db, conversation, role="assistant", content=final_answer)


def stream_chat_turn(
    db: Session,
    current_user: User,
    payload: ChatStreamRequest,
) -> Iterator[ChatStreamEvent]:
    """Yield an SSE stream, preferring LangGraph and falling back to scoped tools."""
    conversation = _get_or_create_conversation(db, current_user, payload.conversation_id)
    conversation_id = str(conversation.id)
    yield {"type": "message_start", "conversation_id": conversation_id, "role": "assistant"}
    current_user_message = _persist_message(db, conversation, role="user", content=payload.message)

    receipt_result: dict[str, object] | None = None
    if payload.receipt_image_base64 is not None:
        receipt_tool_input: dict[str, object] = {
            "filename": payload.receipt_filename or "receipt.jpg",
            "content_type": payload.receipt_content_type or "image/jpeg",
        }
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "analyze_receipt",
            "input": receipt_tool_input,
        }
        receipt_result = build_receipt_candidate(
            db,
            current_user,
            image_base64=payload.receipt_image_base64,
            filename=payload.receipt_filename or "receipt.jpg",
            content_type=payload.receipt_content_type or "image/jpeg",
        )
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Fiş OCR sonucu alındı.",
            tool_name="analyze_receipt",
            tool_calls={"input": receipt_tool_input, "result": receipt_result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "analyze_receipt",
            "result": receipt_result,
        }

    if _wants_investment_advice(payload.message):
        answer = _investment_refusal_answer()
        for chunk in _chunks(answer):
            yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
        _persist_message(db, conversation, role="assistant", content=answer)
        yield {"type": "done", "conversation_id": conversation_id}
        return

    settings = get_settings()
    if _live_agent_available(settings):
        try:
            yield from _stream_live_graph(
                db,
                current_user,
                payload,
                conversation,
                current_user_message=current_user_message,
                receipt_context=_receipt_context(receipt_result) if receipt_result else None,
                settings=settings,
            )
            yield {"type": "done", "conversation_id": conversation_id}
            return
        except Exception:
            fallback_notice = (
                "Canlı koç yolu şu an kullanılamadı; güvenli araç akışıyla devam ediyorum. "
            )
            for chunk in _chunks(fallback_notice):
                yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
    else:
        missing = (
            "OPENROUTER_API_KEY" if settings.llm_provider == "openrouter" else "GEMINI_API_KEY"
        )
        notice = f"{missing} tanımlı değil; güvenli araç akışıyla yanıtlıyorum. "
        for chunk in _chunks(notice):
            yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}

    if receipt_result is not None:
        answer = _receipt_answer(receipt_result)
        for chunk in _chunks(answer):
            yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
        _persist_message(db, conversation, role="assistant", content=answer)
        yield {"type": "done", "conversation_id": conversation_id}
        return

    if _wants_memory(payload.message):
        memory_input: dict[str, object] = {}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "get_user_memory",
            "input": memory_input,
        }
        result = build_user_memory(db, current_user)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Hafıza kayıtları alındı.",
            tool_name="get_user_memory",
            tool_calls={"input": memory_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "get_user_memory",
            "result": result,
        }
        answer = _memory_answer(result)
    elif _wants_visualization(payload.message) and not _wants_concept(payload.message):
        chart_type = "bar"
        if "pasta" in payload.message.casefold():
            chart_type = "pie"
        if _wants_monthly_visualization(payload.message):
            chart_type = "monthly"
        days = 180 if chart_type == "monthly" else 30
        visualize_input: dict[str, object] = {"days": days, "chart_type": chart_type}
        if chart_type == "monthly":
            visualize_input["query"] = payload.message
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "visualize_spending",
            "input": visualize_input,
        }
        result = build_spending_chart(
            db,
            current_user,
            days=days,
            chart_type=chart_type,
            query=payload.message if chart_type == "monthly" else None,
        )
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Harcama grafiği üretildi.",
            tool_name="visualize_spending",
            tool_calls={"input": visualize_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "visualize_spending",
            "result": result,
        }
        answer = _visualization_answer(result)
    elif _wants_subscriptions(payload.message):
        subscription_input: dict[str, object] = {"only_active": True}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "get_subscriptions",
            "input": subscription_input,
        }
        result = build_subscriptions_summary(db, current_user, only_active=True)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Abonelik özeti alındı.",
            tool_name="get_subscriptions",
            tool_calls={"input": subscription_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "get_subscriptions",
            "result": result,
        }
        answer = _subscription_answer(result)
    elif _wants_accumulation_goal_creation(payload.message):
        target_amount = _target_amount_from_message(payload.message)
        if target_amount is None:
            answer = "Birikim hedefi için hedef tutarı yazar mısın? Örneğin 20.000 ₺ gibi."
        else:
            title = _accumulation_title_from_message(payload.message)
            months = _target_months_from_message(payload.message)
            accumulation_input: dict[str, object] = {
                "title": title,
                "target_amount": str(target_amount),
                "target_months": months,
            }
            yield {
                "type": "tool_call",
                "conversation_id": conversation_id,
                "tool_name": "create_accumulation_goal",
                "input": accumulation_input,
            }
            result = build_accumulation_goal_creation(
                db,
                current_user,
                title=title,
                target_amount=target_amount,
                target_months=months,
            )
            _persist_message(
                db,
                conversation,
                role="tool",
                content="Birikim hedefi oluşturuldu.",
                tool_name="create_accumulation_goal",
                tool_calls={"input": accumulation_input, "result": result},
            )
            yield {
                "type": "tool_result",
                "conversation_id": conversation_id,
                "tool_name": "create_accumulation_goal",
                "result": result,
            }
            answer = _accumulation_goal_answer(result, created=True)
    elif _wants_smart_saving_plan(payload.message):
        smart_plan_input: dict[str, object] = {"message": payload.message}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "create_smart_saving_plan",
            "input": smart_plan_input,
        }
        result = build_smart_saving_plan(db, current_user, message=payload.message)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Akıllı hedef planı oluşturuldu.",
            tool_name="create_smart_saving_plan",
            tool_calls={"input": smart_plan_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "create_smart_saving_plan",
            "result": result,
        }
        answer = _smart_saving_plan_answer(result)
    elif _wants_saving_goal_creation(payload.message):
        category = infer_category_from_text(db, current_user, payload.message)
        if category is None:
            answer = "Hangi kategoride tasarruf hedefi oluşturmak istediğini söyler misin?"
        else:
            saving_goal_input: dict[str, object] = {
                "category": category,
                "target_reduction_percent": 15,
            }
            yield {
                "type": "tool_call",
                "conversation_id": conversation_id,
                "tool_name": "create_saving_goal",
                "input": saving_goal_input,
            }
            result = build_saving_goal_creation(
                db,
                current_user,
                category=category,
                target_reduction_percent=15,
            )
            _persist_message(
                db,
                conversation,
                role="tool",
                content="Tasarruf hedefi oluşturuldu.",
                tool_name="create_saving_goal",
                tool_calls={"input": saving_goal_input, "result": result},
            )
            yield {
                "type": "tool_result",
                "conversation_id": conversation_id,
                "tool_name": "create_saving_goal",
                "result": result,
            }
            answer = _saving_goal_answer(result, created=True)
    elif _wants_saving_goal_progress(payload.message):
        category = infer_category_from_text(db, current_user, payload.message)
        saving_goal_input = {"category": category}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "get_saving_goal_progress",
            "input": saving_goal_input,
        }
        result = build_saving_goal_progress(db, current_user, category=category)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Tasarruf hedefi ilerlemesi alındı.",
            tool_name="get_saving_goal_progress",
            tool_calls={"input": saving_goal_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "get_saving_goal_progress",
            "result": result,
        }
        answer = _saving_goal_answer(result, created=False)
    elif _wants_scenario(payload.message):
        scenario_input: dict[str, object] = {"scenario": payload.message}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "simulate_scenario",
            "input": scenario_input,
        }
        result = simulate_finance_scenario(db, current_user, scenario=payload.message)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Senaryo simülasyonu alındı.",
            tool_name="simulate_scenario",
            tool_calls={"input": scenario_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "simulate_scenario",
            "result": result,
        }
        answer = _scenario_answer(result)
    elif _wants_concept(payload.message):
        concept = payload.message
        concept_input: dict[str, object] = {"concept": concept}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "explain_concept",
            "input": concept_input,
        }
        result = explain_finance_concept(current_user, concept=concept)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Kavram açıklaması alındı.",
            tool_name="explain_concept",
            tool_calls={"input": concept_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "explain_concept",
            "result": result,
        }
        answer = _concept_answer(result)
        if _wants_illustration(payload.message):
            illustration_input: dict[str, object] = {"concept": concept}
            yield {
                "type": "tool_call",
                "conversation_id": conversation_id,
                "tool_name": "illustrate_concept",
                "input": illustration_input,
            }
            illustration_result = build_concept_illustration(db, current_user, concept=concept)
            _persist_message(
                db,
                conversation,
                role="tool",
                content="Kavram görseli üretildi.",
                tool_name="illustrate_concept",
                tool_calls={"input": illustration_input, "result": illustration_result},
            )
            yield {
                "type": "tool_result",
                "conversation_id": conversation_id,
                "tool_name": "illustrate_concept",
                "result": illustration_result,
            }
            image_event = _image_event_from_result(
                conversation_id=conversation_id,
                result=illustration_result,
            )
            if image_event is not None:
                yield image_event
            elif "error" in illustration_result:
                answer = f"{answer}\n\nGörsel notu: {illustration_result['error']}"
    else:
        category = infer_category_from_text(db, current_user, payload.message)
        spending_input: dict[str, object] = {"category": category, "days": 30}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "get_spending",
            "input": spending_input,
        }
        result = build_spending_summary(db, current_user, category=category, days=30)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Harcama özeti alındı.",
            tool_name="get_spending",
            tool_calls={"input": spending_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "get_spending",
            "result": result,
        }
        answer = _spending_answer(result)

    for chunk in _chunks(answer):
        yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}

    _persist_message(db, conversation, role="assistant", content=answer)
    yield {"type": "done", "conversation_id": conversation_id}
