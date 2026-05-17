"""Small streaming runner that turns scoped tool results into SSE events."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Any, TypedDict
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agent.graph import build_agent_graph_from_settings
from app.agent.tools import (
    build_accumulation_goal_creation,
    build_concept_illustration,
    build_custom_lesson,
    build_envelope_budget_creation,
    build_envelope_budget_delete,
    build_envelope_budget_overview,
    build_envelope_budget_update,
    build_memory_upsert,
    build_receipt_candidate,
    build_saving_goal_creation,
    build_saving_goal_delete,
    build_saving_goal_progress,
    build_saving_goal_update,
    build_saving_goals_chart,
    build_saving_goals_overview,
    build_spending_chart,
    build_spending_summary,
    build_subscriptions_summary,
    build_user_memory,
    explain_finance_concept,
    infer_category_from_text,
    parse_goal_status_text,
    parse_int_text,
    parse_money_text,
    simulate_finance_scenario,
    visible_categories,
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
    approval_id: str
    action_label: str
    summary: str
    details: list[str]
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
MEMORY_WRITE_PATTERNS = (
    re.compile(r"(?:bunu|şunu|sunu)?\s*hat[ıi]rla\s*[:,-]?\s*(?P<text>.+)", re.IGNORECASE),
    re.compile(r"haf[ıi]zana\s+yaz\s*[:,-]?\s*(?P<text>.+)", re.IGNORECASE),
    re.compile(r"akl[ıi]nda\s+tut\s*[:,-]?\s*(?P<text>.+)", re.IGNORECASE),
    re.compile(r"not\s+al\s*[:,-]?\s*(?P<text>.+)", re.IGNORECASE),
)
CUSTOM_LESSON_HINTS = (
    "özel ders",
    "ozel ders",
    "custom ders",
    "ders oluştur",
    "ders olustur",
    "kendi ders",
)
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
SAVING_GOAL_OVERVIEW_HINTS = (
    "hedeflerimi göster",
    "hedeflerimi goster",
    "hedeflerimi liste",
    "hedeflerim",
    "mevcut hedef",
    "aktif hedef",
    "birikim hedefler",
    "tasarruf hedefler",
)
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
APPROVAL_TOOL_NAMES = {
    "create_saving_goal",
    "create_accumulation_goal",
    "update_saving_goal",
    "delete_saving_goal",
    "create_envelope_budget",
    "update_envelope_budget",
    "delete_envelope_budget",
    "create_smart_saving_plan",
}
APPROVAL_ACTIONS_BY_TOOL = {
    "create_saving_goal": "Tasarruf hedefi oluştur",
    "create_accumulation_goal": "Birikim hedefi oluştur",
    "update_saving_goal": "Hedefi güncelle",
    "delete_saving_goal": "Hedefi sil",
    "create_envelope_budget": "Zarf ekle",
    "update_envelope_budget": "Zarf limitini güncelle",
    "delete_envelope_budget": "Zarfı kapat",
    "create_smart_saving_plan": "Akıllı hedef planı oluştur",
}
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
UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
POSSESSIVE_NAME_PATTERN = re.compile(
    r"\b(?P<name>[A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-Za-zÇĞİÖŞÜçğıöşü]+)?)['’]"
    r"(?:in|ın|un|ün|nin|nın|nun|nün)\b",
    re.IGNORECASE,
)
SCOPE_INJECTION_HINTS = (
    "user_id",
    "kullanıcı id",
    "kullanici id",
    "başka kullanıcı",
    "baska kullanici",
    "başkasının",
    "baskasinin",
    "kullanıcısının",
    "kullanicisinin",
    "onun ver",
)
DATA_ACCESS_HINTS = (
    "veri",
    "harcama",
    "işlem",
    "islem",
    "abonelik",
    "hedef",
    "göster",
    "goster",
    "liste",
    "özet",
    "ozet",
)


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


def _approval_id() -> str:
    return f"approval-{uuid4()}"


def _approval_record(
    *,
    approval_id: str,
    tool_name: str,
    tool_input: dict[str, object],
    action_label: str,
    summary: str,
    details: list[str],
) -> dict[str, object]:
    return {
        "approval_id": approval_id,
        "tool_name": tool_name,
        "input": tool_input,
        "action_label": action_label,
        "summary": summary,
        "details": details,
        "status": "pending",
    }


def _pending_approval_message(
    db: Session,
    conversation: Conversation,
    approval_id: str,
) -> Message | None:
    rows = list(
        db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.role == "tool",
            )
            .order_by(desc(Message.created_at))
            .limit(MAX_CONTEXT_MESSAGES),
        )
        .scalars()
        .all(),
    )
    for message in rows:
        tool_calls = message.tool_calls or {}
        if tool_calls.get("approval_id") == approval_id and tool_calls.get("status") == "pending":
            return message
    return None


def _latest_pending_approval_message(db: Session, conversation: Conversation) -> Message | None:
    rows = list(
        db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.role == "tool",
            )
            .order_by(desc(Message.created_at))
            .limit(MAX_CONTEXT_MESSAGES),
        )
        .scalars()
        .all(),
    )
    for message in rows:
        tool_calls = message.tool_calls or {}
        if tool_calls.get("status") == "pending" and isinstance(tool_calls.get("approval_id"), str):
            return message
    return None


def _approval_from_message(message: Message) -> dict[str, object]:
    return _json_payload(message.tool_calls or {})


def _store_pending_approval(
    db: Session,
    conversation: Conversation,
    approval: dict[str, object],
) -> None:
    _persist_message(
        db,
        conversation,
        role="tool",
        content="Kullanıcı onayı bekleniyor.",
        tool_name=str(approval["tool_name"]),
        tool_calls=approval,
    )


def _mark_approval_status(message: Message, status_value: str) -> None:
    payload = {**(message.tool_calls or {}), "status": status_value}
    message.tool_calls = payload


def _approval_event(conversation_id: str, approval: dict[str, object]) -> ChatStreamEvent:
    details_value = approval.get("details", [])
    details = details_value if isinstance(details_value, list) else []
    return {
        "type": "approval_required",
        "conversation_id": conversation_id,
        "approval_id": str(approval["approval_id"]),
        "tool_name": str(approval["tool_name"]),
        "action_label": str(approval["action_label"]),
        "summary": str(approval["summary"]),
        "details": [str(detail) for detail in details if isinstance(detail, str)],
        "input": _json_payload(approval.get("input", {})),
    }


def _approval_needed_answer() -> str:
    return "Bu işlem verilerini değiştirecek. Onaylıyor musun? Aşağıdaki kartı onaylarsan devam edeceğim."


def _approval_rejected_answer() -> str:
    return "İşlemi iptal ettim; herhangi bir değişiklik yapmadım."


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
    if _wants_custom_lesson(message):
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


def _memory_write_text(message: str) -> str | None:
    stripped = message.strip()
    for pattern in MEMORY_WRITE_PATTERNS:
        match = pattern.search(stripped)
        if match is None:
            continue
        text = " ".join(match.group("text").strip().split())
        return text or None
    return None


def _wants_custom_lesson(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in CUSTOM_LESSON_HINTS)


def _wants_saving_goal_creation(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in SAVING_GOAL_CREATE_HINTS)


def _wants_accumulation_goal_creation(message: str) -> bool:
    normalized = message.casefold()
    return any(hint in normalized for hint in ACCUMULATION_GOAL_CREATE_HINTS)


def _wants_saving_goal_progress(message: str) -> bool:
    normalized = message.casefold()
    return "hedef" in normalized and any(hint in normalized for hint in SAVING_GOAL_PROGRESS_HINTS)


def _wants_saving_goals_overview(message: str) -> bool:
    normalized = message.casefold()
    if any(hint in normalized for hint in SAVING_GOAL_OVERVIEW_HINTS):
        return True
    return "hedef" in normalized and any(
        hint in normalized
        for hint in ("göster", "goster", "liste", "grafik", "görselle", "gorselle")
    )


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


def _normalized_scope_label(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _active_profile_name_labels(current_user: User) -> set[str]:
    normalized_name = _normalized_scope_label(current_user.name)
    if not normalized_name:
        return set()
    labels = {normalized_name}
    labels.update(part for part in normalized_name.split() if part)
    return labels


def _category_name_labels(db: Session, current_user: User) -> set[str]:
    return {
        _normalized_scope_label(category.name) for category in visible_categories(db, current_user)
    }


def _mentions_external_scope_name(db: Session, current_user: User, message: str) -> bool:
    allowed_labels = _active_profile_name_labels(current_user) | _category_name_labels(
        db,
        current_user,
    )
    for match in POSSESSIVE_NAME_PATTERN.finditer(message):
        label = _normalized_scope_label(match.group("name"))
        first_name = label.split()[0] if label else ""
        if label not in allowed_labels and first_name not in allowed_labels:
            return True
    return False


def _wants_scope_injection(db: Session, current_user: User, message: str) -> bool:
    normalized = message.casefold()
    has_data_request = any(hint in normalized for hint in DATA_ACCESS_HINTS)
    if not has_data_request:
        return False
    if UUID_PATTERN.search(normalized):
        return True
    if _mentions_external_scope_name(db, current_user, message):
        return True
    return any(hint in normalized for hint in SCOPE_INJECTION_HINTS)


def _wants_envelope_budget(message: str) -> bool:
    normalized = message.casefold()
    return resolve_envelope_category(message) is not None and any(
        hint in normalized for hint in ENVELOPE_BUDGET_HINTS
    )


def _budget_amount_from_message(message: str) -> Decimal | None:
    return _target_amount_from_message(message)


def _envelope_name_from_message(message: str) -> str | None:
    normalized = message.casefold()
    known = resolve_envelope_category(message)
    if known is not None:
        return known
    patterns = (
        r"([A-Za-zÇĞİÖŞÜçğıöşü0-9\s]{2,40})\s+zarf(?:ı|i|ını|ini|[ıi]n[ıi])\s+"
        r"(?:sil|kapat|güncelle|guncelle|değiştir|degistir)",
        r"([A-Za-zÇĞİÖŞÜçğıöşü0-9\s]{2,40})\s+zarf[ıi]\s+(?:oluştur|olustur|aç|ac|ekle)",
        r"([A-Za-zÇĞİÖŞÜçğıöşü0-9\s]{2,40})\s+için\s+zarf",
        r"zarf\s+(?:oluştur|olustur|aç|ac|ekle)\s+([A-Za-zÇĞİÖŞÜçğıöşü0-9\s]{2,40})",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            value = " ".join((match.group(1) or "").split())
            value = re.sub(r"\b(?:için|icin|limit|bütçe|butce|tl|lira)\b.*$", "", value).strip()
            if len(value) >= 2:
                return value.title()
    return None


def _wants_envelope_mutation(message: str) -> bool:
    normalized = message.casefold()
    return "zarf" in normalized and any(
        hint in normalized
        for hint in (
            "oluştur",
            "olustur",
            "ekle",
            "aç",
            "ac",
            "limit koy",
            "limit belirle",
            "güncelle",
            "guncelle",
            "değiştir",
            "degistir",
            "sil",
            "kapat",
        )
    )


def _goal_title_from_message(message: str) -> str | None:
    normalized = message.casefold()
    patterns = (
        r"([A-Za-zÇĞİÖŞÜçğıöşü0-9\s]{2,60})\s+hedef(?:i|imi|ini|[ıi]n[ıi]|im|in)?\s+"
        r"(?:sil|kaldır|kaldir|duraklat|sürdür|surdur|tamamla|tamamlandı|tamamlandi|"
        r"güncelle|guncelle|değiştir|degistir|katkı|katki)",
        r"hedef(?:i|imi|ini|[ıi]n[ıi]|im|in)?\s+([A-Za-zÇĞİÖŞÜçğıöşü0-9\s]{2,60})\s+"
        r"(?:sil|kaldır|kaldir|duraklat|sürdür|surdur|tamamla|tamamlandı|tamamlandi|"
        r"güncelle|guncelle|değiştir|degistir|katkı|katki)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            value = " ".join((match.group(1) or "").split())
            value = re.sub(r"\b(?:tasarruf|birikim|hedef|hedefi)\b", "", value).strip()
            if len(value) >= 2:
                return value.title()
    return None


def _saving_goal_mutation_approval(
    db: Session,
    current_user: User,
    message: str,
) -> dict[str, object] | None:
    normalized = message.casefold()
    if "hedef" not in normalized:
        return None
    title = _goal_title_from_message(message)
    category = infer_category_from_text(db, current_user, message)
    target_input: dict[str, object] = {
        "title": title,
        "category": category,
    }
    target_input = {key: value for key, value in target_input.items() if value is not None}
    target_label = title or category or "Seçilecek hedef"

    if any(hint in normalized for hint in ("sil", "kaldır", "kaldir")):
        return _approval_record(
            approval_id=_approval_id(),
            tool_name="delete_saving_goal",
            tool_input=target_input,
            action_label="Hedefi sil",
            summary=f"{target_label} hedefi silinecek.",
            details=[
                "Bu işlem hedef kaydını kaldırır.",
                "İşlem defterindeki gelir/gider kayıtları değişmez.",
            ],
        )

    status_value: str | None = None
    status_label: str | None = None
    if any(hint in normalized for hint in ("duraklat", "beklet")):
        status_value = "paused"
        status_label = "duraklatılacak"
    elif any(hint in normalized for hint in ("sürdür", "surdur", "aktif yap", "devam")):
        status_value = "active"
        status_label = "aktif yapılacak"
    elif any(hint in normalized for hint in ("tamamla", "tamamlandı", "tamamlandi", "bitti")):
        status_value = "completed"
        status_label = "tamamlandı yapılacak"

    contribution = _target_amount_from_message(message)
    wants_contribution = any(
        hint in normalized for hint in ("katkı", "katki", "ekle", "biriktirdim")
    )
    if status_value is None and not wants_contribution:
        return None

    tool_input: dict[str, object] = {**target_input}
    details = ["Hedef ilerlemesi güncellenecek."]
    if status_value is not None:
        tool_input["status"] = status_value
        summary = f"{target_label} hedefi {status_label}."
    else:
        summary = f"{target_label} hedefine katkı eklenecek."
    if wants_contribution:
        if contribution is None:
            return None
        tool_input["contribution_amount"] = f"{contribution:.2f}"
        summary = (
            f"{target_label} hedefine {format_amount_text(str(contribution))} katkı eklenecek."
        )
        details.append("Katkı işlem defterine otomatik gelir/gider yazmaz.")
    return _approval_record(
        approval_id=_approval_id(),
        tool_name="update_saving_goal",
        tool_input=tool_input,
        action_label="Hedefi güncelle",
        summary=summary,
        details=details,
    )


def _envelope_mutation_approval(message: str) -> dict[str, object] | None:
    normalized = message.casefold()
    if not _wants_envelope_mutation(message):
        return None
    amount = _budget_amount_from_message(message)
    name = _envelope_name_from_message(message)
    if "sil" in normalized or "kapat" in normalized:
        if name is None:
            return None
        return _approval_record(
            approval_id=_approval_id(),
            tool_name="delete_envelope_budget",
            tool_input={"slug": "__lookup_required__", "name": name},
            action_label="Zarfı kapat",
            summary=f"{name} zarfı aktif profil için kapatılacak.",
            details=["Kategori silinmez.", "Zarf limiti 0,00 ₺ yapılır."],
        )
    if amount is None:
        return None
    if name is None:
        name = "Özel zarf"
    action = (
        "update_envelope_budget"
        if any(h in normalized for h in ("güncelle", "guncelle", "değiştir", "degistir"))
        else "create_envelope_budget"
    )
    return _approval_record(
        approval_id=_approval_id(),
        tool_name=action,
        tool_input={"name": name, "budget_monthly": f"{amount:.2f}"}
        if action == "create_envelope_budget"
        else {"slug": "__lookup_required__", "name": name, "budget_monthly": f"{amount:.2f}"},
        action_label="Zarf limiti kaydet"
        if action == "create_envelope_budget"
        else "Zarf limitini güncelle",
        summary=f"{name} zarfı için aylık limit {format_amount_text(str(amount))} yapılacak.",
        details=[
            "Hazır zarf adıysa mevcut zarf açılır/güncellenir.",
            "Farklı adsa özel zarf oluşturulur.",
        ],
    )


def _mutating_fallback_approval(
    db: Session,
    current_user: User,
    message: str,
) -> dict[str, object] | None:
    envelope = _envelope_mutation_approval(message)
    if envelope is not None:
        return envelope
    if _wants_accumulation_goal_creation(message):
        amount = _target_amount_from_message(message)
        if amount is None:
            return None
        title = _accumulation_title_from_message(message)
        months = _target_months_from_message(message)
        return _approval_record(
            approval_id=_approval_id(),
            tool_name="create_accumulation_goal",
            tool_input={"title": title, "target_amount": f"{amount:.2f}", "target_months": months},
            action_label="Birikim hedefi oluştur",
            summary=f"{title} için {format_amount_text(str(amount))} hedef açılacak.",
            details=[
                f"Hedef süresi yaklaşık {months} ay.",
                "İşlem defterine otomatik gelir/gider yazılmaz.",
            ],
        )
    if _wants_smart_saving_plan(message):
        return _approval_record(
            approval_id=_approval_id(),
            tool_name="create_smart_saving_plan",
            tool_input={"message": message},
            action_label="Akıllı hedef planı oluştur",
            summary="Son 30 gün verisine göre hedef planı oluşturulacak.",
            details=[
                "Uygun kategoriler için tasarruf hedefi açılabilir.",
                "Amaç netse birikim hedefi de açılabilir.",
            ],
        )
    goal_mutation = _saving_goal_mutation_approval(db, current_user, message)
    if goal_mutation is not None:
        return goal_mutation
    if _wants_saving_goal_creation(message):
        return _approval_record(
            approval_id=_approval_id(),
            tool_name="create_saving_goal",
            tool_input={"category": "__infer__", "target_reduction_percent": 15},
            action_label="Tasarruf hedefi oluştur",
            summary="Belirttiğin kategori için %15 azaltma hedefi oluşturulacak.",
            details=[
                "Kategori aktif profil verisinden bulunacak.",
                "Hedef yatırım tavsiyesi değildir.",
            ],
        )
    return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return parse_money_text(value)
    except (InvalidOperation, ValueError):
        return None


def _optional_int(
    value: object,
    *,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    return parse_int_text(
        value if value is not None else default,
        default=default,
        min_value=min_value,
        max_value=max_value,
    )


def _matching_envelope_slug(
    db: Session,
    current_user: User,
    *,
    slug: str | None,
    name: str | None,
) -> str | None:
    if slug and slug != "__lookup_required__":
        return slug
    if not name:
        return None
    overview = build_envelope_budget_overview(db, current_user)
    envelopes = overview.get("envelopes")
    if not isinstance(envelopes, list):
        return None
    normalized_name = _normalized_scope_label(name.removesuffix(" zarfı").removesuffix(" zarf"))
    for item in envelopes:
        if not isinstance(item, dict):
            continue
        labels = [
            _normalized_scope_label(_optional_str(item.get("slug"))),
            _normalized_scope_label(_optional_str(item.get("label"))),
            _normalized_scope_label(_optional_str(item.get("category_name"))),
        ]
        if normalized_name and any(
            label and (normalized_name in label or label in normalized_name) for label in labels
        ):
            return _optional_str(item.get("slug"))
    return None


def _execute_approved_tool(
    db: Session,
    current_user: User,
    tool_name: str,
    tool_input: dict[str, object],
) -> dict[str, object]:
    if tool_name == "create_accumulation_goal":
        target_amount = _optional_decimal(tool_input.get("target_amount"))
        if target_amount is None:
            return {"error": "Birikim hedefi için hedef tutarı net okuyamadım."}
        current_amount = _optional_decimal(tool_input.get("current_amount")) or Decimal("0")
        monthly_contribution = _optional_decimal(tool_input.get("monthly_contribution"))
        target_months = _optional_int(
            tool_input.get("target_months"),
            default=12,
            min_value=1,
            max_value=120,
        )
        return build_accumulation_goal_creation(
            db,
            current_user,
            title=_optional_str(tool_input.get("title")) or "Birikim hedefi",
            target_amount=target_amount,
            current_amount=current_amount,
            target_months=target_months,
            monthly_contribution=monthly_contribution,
        )
    if tool_name == "create_smart_saving_plan":
        return build_smart_saving_plan(
            db,
            current_user,
            message=_optional_str(tool_input.get("message")) or "Akıllı hedef planı",
        )
    if tool_name == "create_saving_goal":
        category = _optional_str(tool_input.get("category"))
        if category == "__infer__":
            category = infer_category_from_text(
                db, current_user, _optional_str(tool_input.get("message")) or ""
            )
        if category is None:
            return {"error": "Hangi kategoride tasarruf hedefi oluşturulacağını netleştiremedim."}
        reduction = _optional_int(
            tool_input.get("target_reduction_percent"),
            default=15,
            min_value=1,
            max_value=50,
        )
        return build_saving_goal_creation(
            db,
            current_user,
            category=category,
            target_reduction_percent=reduction,
        )
    if tool_name == "update_saving_goal":
        return build_saving_goal_update(
            db,
            current_user,
            goal_id=_optional_str(tool_input.get("goal_id")),
            title=_optional_str(tool_input.get("title")),
            category=_optional_str(tool_input.get("category")),
            new_title=_optional_str(tool_input.get("new_title")),
            status=parse_goal_status_text(_optional_str(tool_input.get("status"))),
            current_amount=_optional_decimal(tool_input.get("current_amount")),
            contribution_amount=_optional_decimal(tool_input.get("contribution_amount")),
            monthly_contribution=_optional_decimal(tool_input.get("monthly_contribution")),
        )
    if tool_name == "delete_saving_goal":
        return build_saving_goal_delete(
            db,
            current_user,
            goal_id=_optional_str(tool_input.get("goal_id")),
            title=_optional_str(tool_input.get("title")),
            category=_optional_str(tool_input.get("category")),
        )
    if tool_name == "create_envelope_budget":
        budget = _optional_decimal(tool_input.get("budget_monthly"))
        if budget is None:
            return {"error": "Zarf limitini net okuyamadım."}
        return build_envelope_budget_creation(
            db,
            current_user,
            name=_optional_str(tool_input.get("name")) or "Özel zarf",
            budget_monthly=budget,
        )
    if tool_name == "update_envelope_budget":
        budget = _optional_decimal(tool_input.get("budget_monthly"))
        slug = _matching_envelope_slug(
            db,
            current_user,
            slug=_optional_str(tool_input.get("slug")),
            name=_optional_str(tool_input.get("name")),
        )
        if budget is None:
            return {"error": "Zarf limitini net okuyamadım."}
        if slug is None:
            return {"error": "Güncellenecek zarfı netleştiremedim."}
        return build_envelope_budget_update(db, current_user, slug=slug, budget_monthly=budget)
    if tool_name == "delete_envelope_budget":
        slug = _matching_envelope_slug(
            db,
            current_user,
            slug=_optional_str(tool_input.get("slug")),
            name=_optional_str(tool_input.get("name")),
        )
        if slug is None:
            return {"error": "Kapatılacak zarfı netleştiremedim."}
        return build_envelope_budget_delete(db, current_user, slug=slug)
    return {"error": "Bu işlem için onaylı araç bulunamadı.", "tool_name": tool_name}


def _approved_tool_answer(tool_name: str, result: dict[str, object]) -> str:
    if "error" in result:
        return f"Onayladığın işlemi tamamlayamadım: {result['error']}"
    if tool_name == "create_accumulation_goal":
        return _accumulation_goal_answer(result, created=True)
    if tool_name == "create_saving_goal":
        return _saving_goal_answer(result, created=True)
    if tool_name == "create_smart_saving_plan":
        return _smart_saving_plan_answer(result)
    if tool_name == "update_saving_goal":
        title = str(result.get("title") or "Hedef")
        return f"{title} hedefini güncelledim. Yeni durumu hedefler ekranında görebilirsin."
    if tool_name == "delete_saving_goal":
        title = str(result.get("title") or "Hedef")
        return f"{title} hedefini sildim."
    if tool_name == "create_envelope_budget":
        name = str(result.get("category_name") or "Zarf")
        amount = str(result.get("budget_monthly_formatted") or "0,00 ₺")
        return f"{name} zarfını {amount} aylık limit ile kaydettim."
    if tool_name == "update_envelope_budget":
        name = str(result.get("category_name") or "Zarf")
        amount = str(result.get("budget_monthly_formatted") or "0,00 ₺")
        return f"{name} zarfının aylık limitini {amount} yaptım."
    if tool_name == "delete_envelope_budget":
        name = str(result.get("category_name") or "Zarf")
        return f"{name} zarfını aktif profil için kapattım. Kategori silinmedi; limit 0,00 ₺ oldu."
    return "Onayladığın işlemi tamamladım."


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


def _custom_lesson_field(message: str, key: str) -> str | None:
    for part in message.split("|"):
        if ":" not in part:
            continue
        field_key, value = part.split(":", 1)
        if field_key.strip().casefold() == key.casefold():
            normalized = " ".join(value.split())
            return normalized or None
    return None


def _truthy_lesson_field(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.casefold().strip()
    return normalized not in {"hayır", "hayir", "false", "0", "yok", "istemiyorum"}


def _custom_lesson_input_from_message(message: str) -> dict[str, object]:
    topic = _custom_lesson_field(message, "Konu")
    if topic is None:
        topic = re.sub(
            r"özel ders(?: oluştur| olustur)?|custom ders|ders oluştur|ders olustur",
            "",
            message,
            flags=re.IGNORECASE,
        ).strip(" :.-")
    level = _custom_lesson_field(message, "Seviye") or "beginner"
    duration_text = _custom_lesson_field(message, "Süre") or _custom_lesson_field(message, "Sure")
    duration_match = re.search(r"\d{1,2}", duration_text or "")
    duration_minutes = int(duration_match.group(0)) if duration_match else 5
    include_examples = _truthy_lesson_field(_custom_lesson_field(message, "Örnekler"), default=True)
    include_quiz = _truthy_lesson_field(_custom_lesson_field(message, "Mini quiz"), default=True)
    visual = _truthy_lesson_field(_custom_lesson_field(message, "Görsel"), default=False)
    return {
        "topic": topic or "Finansal okuryazarlık",
        "level": level,
        "duration_minutes": duration_minutes,
        "include_examples": include_examples,
        "include_quiz": include_quiz,
        "visual": visual,
    }


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
    if count == 0:
        return (
            "Aktif abonelik veya tekrarlayan gelir/gider kaydı bulamadım. "
            "Eklediğinde aylık etkisini burada birlikte takip edebiliriz."
        )
    income_total = str(result.get("monthly_income_total_formatted", "0,00 ₺"))
    expense_total = str(result.get("monthly_expense_total_formatted", "0,00 ₺"))
    net_total = str(
        result.get("monthly_net_total_formatted")
        or result.get("monthly_total_formatted")
        or "0,00 ₺"
    )
    return (
        f"Aktif tekrarlayan kayıtların aylık net etkisi {net_total}. "
        f"Düzenli gelir {income_total}, düzenli gider {expense_total}. Toplam {count} kayıt var."
    )


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
        numeric = parse_money_text(value)
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


def _memory_write_answer(result: dict[str, object]) -> str:
    if result.get("saved") is True:
        return "Bunu aktif profilin hafızasına kaydettim. İstersen Hesap > Hafıza ekranından silebilirsin."
    error = str(result.get("error") or "Bu bilgiyi hafızaya kaydedemedim.")
    return error


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


def _scope_refusal_answer() -> str:
    return (
        "Başka bir kullanıcı adı veya user_id ile kapsam değiştiremem. "
        "Yalnızca aktif profilin yetkili veri kapsamındaki bilgileri kullanabilirim. "
        "İstersen aktif profil için harcama, abonelik veya hedef özetini çıkarabilirim."
    )


def _custom_lesson_answer(result: dict[str, object]) -> str:
    if "error" in result:
        return str(result["error"])
    title = str(result.get("title") or "Özel ders")
    duration = result.get("duration_minutes")
    goals = result.get("learning_goals")
    sections = result.get("sections")
    examples = result.get("examples")
    quiz = result.get("mini_quiz")
    lines = [f"### {title}", f"Süre: {duration} dakika.", ""]
    if isinstance(goals, list) and goals:
        lines.append("**Bu derste hedef:**")
        lines.extend(f"- {goal}" for goal in goals[:3])
        lines.append("")
    if isinstance(sections, list) and sections:
        lines.append("**Ders akışı:**")
        for index, section in enumerate(sections[:4], start=1):
            if not isinstance(section, dict):
                continue
            section_title = str(section.get("title") or "Bölüm")
            minutes = section.get("minutes")
            content = str(section.get("content") or "")
            lines.append(f"{index}. **{section_title}** ({minutes} dk)")
            if content:
                lines.append(content)
            lines.append("")
    if isinstance(examples, list) and examples:
        lines.append("**Örnekler:**")
        lines.extend(f"- {example}" for example in examples[:3])
        lines.append("")
    if isinstance(quiz, list) and quiz:
        lines.append("**Mini quiz:**")
        for index, item in enumerate(quiz[:2], start=1):
            if isinstance(item, dict):
                question = str(item.get("question") or "").strip()
                if question:
                    lines.append(f"{index}. {question}")
        lines.append("Cevaplarını yazarsan birlikte kontrol edip doğrulayabilirim.")
        lines.append("")
    safety_note = result.get("safety_note")
    if isinstance(safety_note, str):
        lines.append(safety_note)
    return "\n".join(lines).strip()


def _saving_goals_overview_answer(result: dict[str, object]) -> str:
    count = _int_result(result, "count") if "count" in result else 0
    goals = result.get("goals")
    if count == 0 or not isinstance(goals, list):
        return (
            "Aktif birikim veya tasarruf hedefi bulamadım. İstersen sohbetten yeni hedef "
            "oluşturabilirim; örneğin 'Tatil için 30.000 TL birikim hedefi oluştur.'"
        )

    lines = [f"Aktif {count} hedefin var. Grafiği hemen üstte görebilirsin."]
    for item in goals[:4]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Hedef")
        progress_decimal = _decimal_result(item, "progress_percent") or Decimal("0")
        progress = f"{min(max(progress_decimal, Decimal('0')), Decimal('100')):.1f}"
        if item.get("goal_type") == "accumulation":
            target = str(item.get("target_amount_formatted") or "0,00 ₺")
            current = str(item.get("current_amount_formatted") or "0,00 ₺")
            remaining = str(item.get("remaining_amount_formatted") or "0,00 ₺")
            lines.append(
                f"{title}: {target} hedefin %{progress} tamamlandı; şu an {current}, kalan {remaining}."
            )
        else:
            category = str(item.get("category_name") or "Kategori")
            target = str(item.get("target_spending_amount_formatted") or "0,00 ₺")
            actual = str(item.get("actual_spending_formatted") or "0,00 ₺")
            remaining = str(item.get("remaining_limit_formatted") or "0,00 ₺")
            lines.append(
                f"{category}: bu ay hedef limit {target}; şu ana kadar {actual}, kalan limit {remaining}."
            )
    lines.append("Detay için /dashboard/goals sayfasında hedef kartına tıklayabilirsin.")
    return " ".join(lines)


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


def _approval_summary_for_tool(tool_name: str, tool_input: dict[str, object]) -> str:
    if tool_name == "create_saving_goal":
        category = _optional_str(tool_input.get("category")) or "Seçilecek kategori"
        reduction = _optional_str(tool_input.get("target_reduction_percent")) or "15"
        return f"{category} kategorisi için %{reduction} azaltma hedefi oluşturulacak."
    if tool_name == "create_accumulation_goal":
        title = _optional_str(tool_input.get("title")) or "Birikim hedefi"
        amount = _optional_str(tool_input.get("target_amount"))
        amount_text = format_amount_text(amount) if amount else "hedef tutar"
        return f"{title} için {amount_text} hedef açılacak."
    if tool_name == "create_smart_saving_plan":
        return "Son 30 gün verisine göre hedef planı oluşturulacak."
    if tool_name == "update_saving_goal":
        title = (
            _optional_str(tool_input.get("title"))
            or _optional_str(tool_input.get("category"))
            or "Seçilecek hedef"
        )
        return f"{title} hedefi güncellenecek."
    if tool_name == "delete_saving_goal":
        title = (
            _optional_str(tool_input.get("title"))
            or _optional_str(tool_input.get("category"))
            or "Seçilecek hedef"
        )
        return f"{title} hedefi silinecek."
    if tool_name == "create_envelope_budget":
        name = _optional_str(tool_input.get("name")) or "Yeni zarf"
        amount = _optional_str(tool_input.get("budget_monthly"))
        amount_text = format_amount_text(amount) if amount else "aylık limit"
        return f"{name} zarfı için aylık limit {amount_text} yapılacak."
    if tool_name == "update_envelope_budget":
        name = (
            _optional_str(tool_input.get("name"))
            or _optional_str(tool_input.get("slug"))
            or "Seçilecek zarf"
        )
        amount = _optional_str(tool_input.get("budget_monthly"))
        amount_text = format_amount_text(amount) if amount else "aylık limit"
        return f"{name} zarfı için aylık limit {amount_text} yapılacak."
    if tool_name == "delete_envelope_budget":
        name = (
            _optional_str(tool_input.get("name"))
            or _optional_str(tool_input.get("slug"))
            or "Seçilecek zarf"
        )
        return f"{name} zarfı aktif profil için kapatılacak."
    return "Bu işlem aktif profil verilerini değiştirecek."


def _approval_details_for_tool(tool_name: str) -> list[str]:
    if tool_name == "create_envelope_budget":
        return [
            "Hazır zarf adıysa mevcut zarf açılır/güncellenir.",
            "Farklı adsa özel zarf oluşturulur.",
        ]
    if tool_name == "update_envelope_budget":
        return ["Zarf limiti aktif profil için güncellenir."]
    if tool_name == "delete_envelope_budget":
        return ["Kategori silinmez.", "Zarf limiti 0,00 ₺ yapılır."]
    if tool_name in {"create_accumulation_goal", "update_saving_goal"}:
        return ["İşlem defterine otomatik gelir/gider yazılmaz."]
    if tool_name == "delete_saving_goal":
        return [
            "Bu işlem hedef kaydını kaldırır.",
            "İşlem defterindeki gelir/gider kayıtları değişmez.",
        ]
    if tool_name == "create_smart_saving_plan":
        return [
            "Uygun kategoriler için tasarruf hedefi açılabilir.",
            "Amaç netse birikim hedefi de açılabilir.",
        ]
    return ["Hedef yatırım tavsiyesi değildir."]


def _approval_from_tool_call(tool_name: str, tool_input: dict[str, object]) -> dict[str, object]:
    return _approval_record(
        approval_id=_approval_id(),
        tool_name=tool_name,
        tool_input=tool_input,
        action_label=APPROVAL_ACTIONS_BY_TOOL.get(tool_name, "İşlemi onayla"),
        summary=_approval_summary_for_tool(tool_name, tool_input),
        details=_approval_details_for_tool(tool_name),
    )


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
                        if tool_name in APPROVAL_TOOL_NAMES:
                            approval = _approval_from_tool_call(tool_name, tool_input)
                            _store_pending_approval(db, conversation, approval)
                            answer = _approval_needed_answer()
                            for chunk in _chunks(answer):
                                yield {
                                    "type": "delta",
                                    "conversation_id": str(conversation.id),
                                    "content": chunk,
                                }
                            yield _approval_event(str(conversation.id), approval)
                            _persist_message(db, conversation, role="assistant", content=answer)
                            return
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

    if payload.approval_decision is not None:
        if payload.approval_id is None:
            answer = "Onay bilgisini eşleştiremedim; işlemi çalıştırmadım."
            for chunk in _chunks(answer):
                yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
            _persist_message(db, conversation, role="assistant", content=answer)
            yield {"type": "done", "conversation_id": conversation_id}
            return
        approval_message = _pending_approval_message(db, conversation, payload.approval_id)
        if approval_message is None:
            answer = "Bu onay isteği artık geçerli değil; herhangi bir değişiklik yapmadım."
            for chunk in _chunks(answer):
                yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
            _persist_message(db, conversation, role="assistant", content=answer)
            yield {"type": "done", "conversation_id": conversation_id}
            return
        approval = _approval_from_message(approval_message)
        tool_name = str(approval.get("tool_name") or approval_message.tool_name or "")
        tool_input = _json_payload(approval.get("input", {}))
        if payload.approval_decision == "rejected":
            _mark_approval_status(approval_message, "rejected")
            db.commit()
            answer = _approval_rejected_answer()
            for chunk in _chunks(answer):
                yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
            _persist_message(db, conversation, role="assistant", content=answer)
            yield {"type": "done", "conversation_id": conversation_id}
            return
        _mark_approval_status(approval_message, "approved")
        db.commit()
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": tool_name,
            "input": tool_input,
        }
        result = _execute_approved_tool(db, current_user, tool_name, tool_input)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Onaylanan araç sonucu alındı.",
            tool_name=tool_name,
            tool_calls={"input": tool_input, "result": result, "approval_id": payload.approval_id},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": tool_name,
            "result": result,
        }
        answer = _approved_tool_answer(tool_name, result)
        for chunk in _chunks(answer):
            yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
        _persist_message(db, conversation, role="assistant", content=answer)
        yield {"type": "done", "conversation_id": conversation_id}
        return

    latest_pending_approval = _latest_pending_approval_message(db, conversation)
    if latest_pending_approval is not None:
        approval = _approval_from_message(latest_pending_approval)
        answer = "Önce bekleyen onay kartını yanıtlaman gerekiyor; yeni değişiklik yapmadım."
        for chunk in _chunks(answer):
            yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
        yield _approval_event(conversation_id, approval)
        _persist_message(db, conversation, role="assistant", content=answer)
        yield {"type": "done", "conversation_id": conversation_id}
        return

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

    if _wants_scope_injection(db, current_user, payload.message):
        answer = _scope_refusal_answer()
        for chunk in _chunks(answer):
            yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
        _persist_message(db, conversation, role="assistant", content=answer)
        yield {"type": "done", "conversation_id": conversation_id}
        return

    if _wants_investment_advice(payload.message):
        answer = _investment_refusal_answer()
        for chunk in _chunks(answer):
            yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
        _persist_message(db, conversation, role="assistant", content=answer)
        yield {"type": "done", "conversation_id": conversation_id}
        return

    pending_approval = _mutating_fallback_approval(db, current_user, payload.message)
    if pending_approval is not None:
        if pending_approval["tool_name"] == "create_saving_goal":
            tool_input = _json_payload(pending_approval.get("input", {}))
            category = infer_category_from_text(db, current_user, payload.message)
            if category is None:
                answer = "Hangi kategoride tasarruf hedefi oluşturmak istediğini söyler misin?"
                for chunk in _chunks(answer):
                    yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
                _persist_message(db, conversation, role="assistant", content=answer)
                yield {"type": "done", "conversation_id": conversation_id}
                return
            pending_approval["input"] = {
                **tool_input,
                "category": category,
                "message": payload.message,
            }
            pending_approval["summary"] = (
                f"{category} kategorisi için %15 azaltma hedefi oluşturulacak."
            )
        _store_pending_approval(db, conversation, pending_approval)
        answer = _approval_needed_answer()
        for chunk in _chunks(answer):
            yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
        yield _approval_event(conversation_id, pending_approval)
        _persist_message(db, conversation, role="assistant", content=answer)
        yield {"type": "done", "conversation_id": conversation_id}
        return

    if _wants_custom_lesson(payload.message):
        lesson_input = _custom_lesson_input_from_message(payload.message)
        duration_value = lesson_input["duration_minutes"]
        duration_minutes = (
            duration_value if isinstance(duration_value, int) else int(str(duration_value))
        )
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "create_custom_lesson",
            "input": lesson_input,
        }
        result = build_custom_lesson(
            current_user,
            topic=str(lesson_input["topic"]),
            level=str(lesson_input["level"]),
            duration_minutes=duration_minutes,
            include_examples=bool(lesson_input["include_examples"]),
            include_quiz=bool(lesson_input["include_quiz"]),
            visual=bool(lesson_input["visual"]),
        )
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Özel ders taslağı oluşturuldu.",
            tool_name="create_custom_lesson",
            tool_calls={"input": lesson_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "create_custom_lesson",
            "result": result,
        }
        if result.get("error") is None and lesson_input.get("visual") is True:
            concept = str(result.get("illustration_prompt") or lesson_input["topic"])
            lesson_illustration_input: dict[str, object] = {"concept": concept}
            yield {
                "type": "tool_call",
                "conversation_id": conversation_id,
                "tool_name": "illustrate_concept",
                "input": lesson_illustration_input,
            }
            image_result = build_concept_illustration(db, current_user, concept=concept)
            _persist_message(
                db,
                conversation,
                role="tool",
                content="Özel ders görseli hazırlandı.",
                tool_name="illustrate_concept",
                tool_calls={"input": lesson_illustration_input, "result": image_result},
            )
            yield {
                "type": "tool_result",
                "conversation_id": conversation_id,
                "tool_name": "illustrate_concept",
                "result": image_result,
            }
            image_event = _image_event_from_result(
                conversation_id=conversation_id,
                result=image_result,
            )
            if image_event is not None:
                yield image_event
        answer = _custom_lesson_answer(result)
        for chunk in _chunks(answer):
            yield {"type": "delta", "conversation_id": conversation_id, "content": chunk}
        _persist_message(db, conversation, role="assistant", content=answer)
        yield {"type": "done", "conversation_id": conversation_id}
        return

    memory_text = _memory_write_text(payload.message)
    if memory_text is not None:
        memory_write_input: dict[str, object] = {"text": memory_text}
        result = build_memory_upsert(db, current_user, text=memory_text)
        memory_trace_input: dict[str, object] = (
            {"text": "[redacted]"} if result.get("blocked") is True else memory_write_input
        )
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "remember_user_memory",
            "input": memory_trace_input,
        }
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Hafıza kaydı güncellendi."
            if result.get("saved")
            else "Hafıza kaydı reddedildi.",
            tool_name="remember_user_memory",
            tool_calls={"input": memory_trace_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "remember_user_memory",
            "result": result,
        }
        answer = _memory_write_answer(result)
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
        memory_read_input: dict[str, object] = {}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "get_user_memory",
            "input": memory_read_input,
        }
        result = build_user_memory(db, current_user)
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Hafıza kayıtları alındı.",
            tool_name="get_user_memory",
            tool_calls={"input": memory_read_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "get_user_memory",
            "result": result,
        }
        answer = _memory_answer(result)
    elif _wants_saving_goals_overview(payload.message):
        goals_input: dict[str, object] = {"status": "active"}
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "get_saving_goals",
            "input": goals_input,
        }
        overview_result = build_saving_goals_overview(db, current_user, status="active")
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Hedef özeti alındı.",
            tool_name="get_saving_goals",
            tool_calls={"input": goals_input, "result": overview_result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "get_saving_goals",
            "result": overview_result,
        }
        yield {
            "type": "tool_call",
            "conversation_id": conversation_id,
            "tool_name": "visualize_saving_goals",
            "input": goals_input,
        }
        result = build_saving_goals_chart(db, current_user, status="active")
        _persist_message(
            db,
            conversation,
            role="tool",
            content="Hedef grafiği üretildi.",
            tool_name="visualize_saving_goals",
            tool_calls={"input": goals_input, "result": result},
        )
        yield {
            "type": "tool_result",
            "conversation_id": conversation_id,
            "tool_name": "visualize_saving_goals",
            "result": result,
        }
        answer = _saving_goals_overview_answer(result)
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
