from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.config import Settings
from app.models.category import Category
from app.models.user import User
from app.routers.receipts import upload_receipt
from app.services.minio import StoredReceipt
from app.services.ocr import (
    LlmReceiptPayload,
    ReceiptOcrService,
    ReceiptOcrUnavailableError,
    _invoke_vision_model,
    openrouter_headers,
)


class FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._items)


class FakeSession:
    def __init__(self, categories: list[Category]) -> None:
        self.categories = categories

    def execute(self, _statement: object) -> FakeResult:
        return FakeResult(self.categories)


class FakeStorage:
    def save_receipt(
        self,
        *,
        user_id: UUID,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> StoredReceipt:
        assert user_id
        assert filename == "migros_demo.txt"
        assert content_type == "text/plain"
        assert b"GENEL TOPLAM" in content
        return StoredReceipt(
            object_name=f"receipts/{user_id}/migros_demo.txt",
            public_url="http://localhost:9000/receipts/migros_demo.txt",
        )


def make_user() -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        name="Test Kullanıcı",
        role="individual",
        parent_id=None,
        password_hash="hash",
        birth_date=date(1991, 1, 1),
        finance_level="beginner",
        is_demo=False,
    )
    user.children = []
    return user


def make_category(name: str) -> Category:
    return Category(
        id=uuid4(),
        user_id=None,
        name=name,
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )


def sample_receipt_bytes() -> bytes:
    path = Path(__file__).parents[2] / "seeds" / "sample_receipts" / "migros_demo.txt"
    return path.read_bytes()


def test_text_receipt_parser_returns_stable_migros_candidate() -> None:
    service = ReceiptOcrService(Settings(app_env="test", jwt_secret="test-secret-test-secret"))
    category = make_category("Market")

    result = service.analyze(
        content=sample_receipt_bytes(),
        content_type="text/plain",
        filename="migros_demo.txt",
        receipt_image_url="http://localhost:9000/receipts/migros_demo.txt",
        categories=[category],
    )

    assert result.merchant == "MIGROS TICARET A.S."
    assert result.amount == Decimal("247.50")
    assert result.category_id == category.id
    assert result.category_name == "Market"
    assert result.occurred_at == datetime.fromisoformat("2026-05-12T14:32:00+03:00")
    assert result.raw_ocr_data["provider"] == "local_text"
    assert len(result.items) == 4


def test_openrouter_ocr_headers_are_ascii_safe() -> None:
    settings = Settings(
        app_env="test",
        jwt_secret="test-secret-test-secret",
        openrouter_http_referer="http://localhost:3000",
        openrouter_app_title="Cüzdan Koçu",
    )

    headers = openrouter_headers(settings)

    assert headers == {
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Cuzdan Kocu",
    }
    for value in headers.values():
        value.encode("ascii")


class FailingVisionModel:
    def invoke(self, _messages: object) -> object:
        raise UnicodeEncodeError("ascii", "ü", 0, 1, "ordinal not in range")


class FakeVisionResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class TurkishDecimalVisionModel:
    def invoke(self, _messages: object) -> FakeVisionResponse:
        return FakeVisionResponse(
            """
            {
              "merchant": "MIGROS TICARET A.S.",
              "total": "1.247,50 TL",
              "date": "12.05.2026 14.32",
              "items": [
                {"name": "Süt", "quantity": "1,5", "amount": "247,50 ₺"},
                {"name": "Peynir", "amount": "1.000"}
              ],
              "confidence": "85%"
            }
            """,
        )


def test_vision_provider_errors_become_ocr_unavailable() -> None:
    with pytest.raises(ReceiptOcrUnavailableError):
        _invoke_vision_model(
            FailingVisionModel(),  # type: ignore[arg-type]
            content=b"fake-image",
            content_type="image/png",
            filename="fis.png",
        )


def test_llm_receipt_payload_accepts_turkish_decimal_text() -> None:
    payload = LlmReceiptPayload.model_validate(
        {
            "merchant": "Migros",
            "total_amount": "1.247,50 TL",
            "items": [
                {"name": "Süt", "quantity": "1,5", "amount": "247,50 ₺"},
                {"name": "Peynir", "amount": "1.000"},
            ],
            "confidence": "0,85",
        },
    )

    assert payload.total_amount == Decimal("1247.50")
    assert payload.confidence == Decimal("0.85")
    assert payload.items[0].quantity == Decimal("1.5")
    assert payload.items[0].amount == Decimal("247.50")
    assert payload.items[1].amount == Decimal("1000")


def test_llm_receipt_payload_accepts_common_model_aliases() -> None:
    payload = LlmReceiptPayload.model_validate(
        {
            "merchant": "Migros",
            "total": "1.247,50 TL",
            "date": "12.05.2026 14.32",
            "confidence": "85%",
        },
    )

    assert payload.total_amount == Decimal("1247.50")
    assert payload.occurred_at == datetime.fromisoformat("2026-05-12T14:32:00+03:00")
    assert payload.confidence == Decimal("0.85")


def test_llm_receipt_payload_accepts_discount_item_amounts() -> None:
    payload = LlmReceiptPayload.model_validate(
        {
            "merchant": "Migros",
            "total_amount": "247,50",
            "items": [
                {"name": "Poşet", "amount": "0,00"},
                {"name": "Kampanya indirimi", "amount": "-10,00"},
            ],
        },
    )

    assert payload.total_amount == Decimal("247.50")
    assert payload.items[0].amount == Decimal("0.00")
    assert payload.items[1].amount == Decimal("-10.00")


def test_vision_response_accepts_turkish_decimal_text() -> None:
    payload = _invoke_vision_model(
        TurkishDecimalVisionModel(),  # type: ignore[arg-type]
        content=b"fake-image",
        content_type="image/png",
        filename="fis.png",
    )

    assert payload.total_amount == Decimal("1247.50")
    assert payload.occurred_at == datetime.fromisoformat("2026-05-12T14:32:00+03:00")
    assert payload.confidence == Decimal("0.85")
    assert payload.items[0].amount == Decimal("247.50")
    assert payload.items[1].amount == Decimal("1000")


@pytest.mark.asyncio
async def test_upload_receipt_returns_candidate_without_writing_transaction() -> None:
    user = make_user()
    category = make_category("Market")
    upload = UploadFile(
        BytesIO(sample_receipt_bytes()),
        filename="migros_demo.txt",
        headers=Headers({"content-type": "text/plain"}),
    )

    result = await upload_receipt(
        file=upload,
        db=FakeSession([category]),
        current_user=user,
        storage=FakeStorage(),
        ocr=ReceiptOcrService(Settings(app_env="test", jwt_secret="test-secret-test-secret")),
    )

    assert result.amount == Decimal("247.50")
    assert result.receipt_image_url.endswith("migros_demo.txt")
    assert result.description == "MIGROS TICARET A.S. fişi"
