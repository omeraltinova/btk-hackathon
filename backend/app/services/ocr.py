"""Receipt OCR and structured parsing service."""

from __future__ import annotations

import base64
import json
import re
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal
from zoneinfo import ZoneInfo

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import Settings, get_settings
from app.models.category import Category
from app.schemas.receipt import ReceiptCandidateRead, ReceiptItemRead

ISTANBUL = ZoneInfo("Europe/Istanbul")
MONEY_QUANT = Decimal("0.01")
TURKISH_ASCII_TRANSLATION = str.maketrans(
    {
        "ç": "c",
        "Ç": "C",
        "ğ": "g",
        "Ğ": "G",
        "ı": "i",
        "İ": "I",
        "ö": "o",
        "Ö": "O",
        "ş": "s",
        "Ş": "S",
        "ü": "u",
        "Ü": "U",
    },
)


class ReceiptOcrError(RuntimeError):
    """Raised when OCR output cannot be parsed into a receipt candidate."""


class ReceiptOcrUnavailableError(RuntimeError):
    """Raised when no OCR provider is configured for image input."""


class LlmReceiptItem(BaseModel):
    name: str = Field(min_length=1)
    quantity: Decimal | None = None
    amount: Decimal | None = Field(default=None, gt=0)


class LlmReceiptPayload(BaseModel):
    merchant: str | None = None
    total_amount: Decimal = Field(gt=0)
    occurred_at: datetime | None = None
    raw_text: str | None = None
    items: list[LlmReceiptItem] = Field(default_factory=list)
    confidence: Decimal = Field(default=Decimal("0.70"), ge=0, le=1)

    @field_validator("merchant", "raw_text")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class ReceiptOcrService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def analyze(
        self,
        *,
        content: bytes,
        content_type: str,
        filename: str,
        receipt_image_url: str,
        categories: Iterable[Category],
    ) -> ReceiptCandidateRead:
        text = _extract_text_payload(content, content_type)
        if text is not None:
            payload = _parse_text_receipt(text)
            provider: Literal["local_text", "gemini", "openrouter"] = "local_text"
        else:
            payload = self._analyze_image_with_llm(
                content=content,
                content_type=content_type,
                filename=filename,
            )
            provider = self._settings.llm_provider

        category = _suggest_category(payload, categories)
        occurred_at = _aware_istanbul(payload.occurred_at or datetime.now(ISTANBUL))
        items = [
            ReceiptItemRead(
                name=item.name, quantity=item.quantity, amount=_money_or_none(item.amount)
            )
            for item in payload.items[:20]
        ]
        raw_ocr_data = {
            "provider": provider,
            "merchant": payload.merchant,
            "total_amount": _decimal_text(payload.total_amount),
            "occurred_at": occurred_at.isoformat(),
            "raw_text": payload.raw_text,
            "items": [
                {
                    "name": item.name,
                    "quantity": _decimal_text(item.quantity) if item.quantity is not None else None,
                    "amount": _decimal_text(item.amount) if item.amount is not None else None,
                }
                for item in items
            ],
            "source_filename": filename,
        }

        merchant = payload.merchant
        description = f"{merchant} fişi" if merchant else "Fişten aktarılan gider"
        return ReceiptCandidateRead(
            merchant=merchant,
            amount=_money(payload.total_amount),
            occurred_at=occurred_at,
            category_id=category.id if category else None,
            category_name=category.name if category else None,
            description=description,
            receipt_image_url=receipt_image_url,
            raw_ocr_data=raw_ocr_data,
            items=items,
            confidence=payload.confidence.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )

    def _analyze_image_with_llm(
        self,
        *,
        content: bytes,
        content_type: str,
        filename: str,
    ) -> LlmReceiptPayload:
        model: BaseChatModel
        if self._settings.llm_provider == "openrouter":
            if not self._settings.openrouter_api_key:
                raise ReceiptOcrUnavailableError("OPENROUTER_API_KEY is not configured.")
            model = ChatOpenAI(
                model=self._settings.openrouter_model,
                api_key=self._settings.openrouter_api_key,
                base_url=self._settings.openrouter_base_url,
                temperature=0,
                default_headers=openrouter_headers(self._settings),
            )
        else:
            if not self._settings.gemini_api_key:
                raise ReceiptOcrUnavailableError("GEMINI_API_KEY is not configured.")
            model = ChatGoogleGenerativeAI(
                model=self._settings.gemini_model,
                api_key=self._settings.gemini_api_key,
                temperature=0,
            )
        return _invoke_vision_model(
            model, content=content, content_type=content_type, filename=filename
        )


def openrouter_headers(settings: Settings) -> dict[str, str] | None:
    headers: dict[str, str] = {}
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = ascii_header(settings.openrouter_http_referer)
    if settings.openrouter_app_title:
        headers["X-Title"] = ascii_header(settings.openrouter_app_title)
    return headers or None


def ascii_header(value: str) -> str:
    translated = value.translate(TURKISH_ASCII_TRANSLATION)
    normalized = unicodedata.normalize("NFKD", translated)
    header_value = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(header_value.split()) or "Cuzdan Kocu"


def _invoke_vision_model(
    model: BaseChatModel,
    *,
    content: bytes,
    content_type: str,
    filename: str,
) -> LlmReceiptPayload:
    encoded = base64.b64encode(content).decode("ascii")
    prompt = (
        "Extract this Turkish receipt as strict JSON only. "
        "Schema: merchant string|null, total_amount decimal string, "
        "occurred_at ISO-8601 string|null, raw_text string|null, "
        "items array of {name, quantity, amount}, confidence decimal 0..1. "
        f"Filename: {filename}."
    )
    try:
        response = model.invoke(
            [
                HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                        },
                    ],
                ),
            ],
        )
    except Exception as exc:
        raise ReceiptOcrUnavailableError("Receipt OCR provider request failed.") from exc
    try:
        parsed = json.loads(_extract_json_object(_message_content_text(response.content)))
        return LlmReceiptPayload.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError, InvalidOperation) as exc:
        raise ReceiptOcrError("Receipt OCR response could not be parsed.") from exc


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, str):
                pieces.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                pieces.append(str(item["text"]))
        return "\n".join(pieces)
    return str(content)


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ReceiptOcrError("Receipt OCR response did not include JSON.")
    return stripped[start : end + 1]


def _extract_text_payload(content: bytes, content_type: str) -> str | None:
    if content_type.startswith("text/"):
        return content.decode("utf-8", errors="ignore")
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    printable_ratio = sum(1 for char in decoded if char.isprintable() or char.isspace()) / max(
        len(decoded),
        1,
    )
    keywords = ("toplam", "fis", "fiş", "tarih", "kdv", "tl", "₺")
    if printable_ratio > 0.9 and any(keyword in decoded.casefold() for keyword in keywords):
        return decoded
    return None


def _parse_text_receipt(text: str) -> LlmReceiptPayload:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    total = _find_total(lines)
    if total is None:
        raise ReceiptOcrError("Receipt total could not be found.")
    merchant = _find_merchant(lines)
    occurred_at = _find_date(lines)
    items = _find_items(lines)
    return LlmReceiptPayload(
        merchant=merchant,
        total_amount=total,
        occurred_at=occurred_at,
        raw_text=text,
        items=items,
        confidence=Decimal("0.82"),
    )


def _find_merchant(lines: list[str]) -> str | None:
    ignored = ("tarih", "fis", "fiş", "kdv", "toplam", "mersis", "tel", "adres")
    for line in lines[:8]:
        normalized = line.casefold()
        if not any(token in normalized for token in ignored) and not _amount_pattern().search(line):
            return " ".join(line.split())[:120]
    return None


def _find_total(lines: list[str]) -> Decimal | None:
    total_keywords = ("genel toplam", "toplam", "tutar", "nakit")
    for line in reversed(lines):
        normalized = line.casefold()
        if any(keyword in normalized for keyword in total_keywords):
            amount = _last_amount(line)
            if amount is not None:
                return amount
    return None


def _find_date(lines: list[str]) -> datetime | None:
    date_regex = re.compile(
        r"(?P<day>\d{1,2})[./-](?P<month>\d{1,2})[./-](?P<year>\d{4})"
        r"(?:\s+(?P<hour>\d{1,2})[:.](?P<minute>\d{2}))?"
    )
    for line in lines:
        match = date_regex.search(line)
        if match is None:
            continue
        return datetime(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            int(match.group("hour") or 12),
            int(match.group("minute") or 0),
            tzinfo=ISTANBUL,
        )
    return None


def _find_items(lines: list[str]) -> list[LlmReceiptItem]:
    ignored = ("toplam", "tarih", "kdv", "nakit", "fis", "fiş", "ara toplam")
    items: list[LlmReceiptItem] = []
    for line in lines:
        normalized = line.casefold()
        if any(token in normalized for token in ignored):
            continue
        amount = _last_amount(line)
        if amount is None:
            continue
        name = _amount_pattern().sub("", line).strip(" -:*\t")
        if len(name) < 2:
            continue
        items.append(LlmReceiptItem(name=name[:80], amount=amount))
    return items


def _last_amount(text: str) -> Decimal | None:
    matches = _amount_pattern().findall(text)
    if not matches:
        return None
    return _parse_decimal(matches[-1])


def _amount_pattern() -> re.Pattern[str]:
    return re.compile(r"(?<!\d)(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2}|\.\d{2})(?!\d)")


def _parse_decimal(value: str) -> Decimal | None:
    cleaned = value.strip().replace("₺", "").replace("TL", "").replace("tl", "").strip()
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return _money(Decimal(cleaned))
    except InvalidOperation:
        return None


def _suggest_category(
    payload: LlmReceiptPayload, categories: Iterable[Category]
) -> Category | None:
    haystack = f"{payload.merchant or ''} {payload.raw_text or ''}".casefold()
    aliases = [
        ("Market", ("migros", "bim", "a101", "şok", "sok", "carrefour", "market")),
        ("Yeme İçme", ("restoran", "restaurant", "cafe", "kahve", "yemek")),
        ("Ulaşım", ("akaryakıt", "benzin", "metro", "otobüs", "taksi", "taxi")),
        ("Sağlık", ("eczane", "ilaç", "hastane")),
        ("Fatura", ("fatura", "elektrik", "doğalgaz", "su faturası", "internet")),
    ]
    category_list = list(categories)
    for canonical, hints in aliases:
        if any(hint in haystack for hint in hints):
            matched = _find_category(category_list, canonical)
            if matched is not None:
                return matched
    for category in category_list:
        if category.name.casefold() in haystack:
            return category
    return None


def _find_category(categories: Iterable[Category], name: str) -> Category | None:
    target = name.casefold()
    for category in categories:
        if category.name.casefold() == target:
            return category
    return None


def _aware_istanbul(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=ISTANBUL)
    return value.astimezone(ISTANBUL)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _money_or_none(value: Decimal | None) -> Decimal | None:
    return _money(value) if value is not None else None


def _decimal_text(value: Decimal) -> str:
    return f"{value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP):.2f}"
