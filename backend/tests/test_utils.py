from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.utils.date_format import format_tr_date
from app.utils.tl_format import format_tl


def test_format_tl_uses_turkish_lira_format() -> None:
    assert format_tl(Decimal("1250.5")) == "1.250,50 ₺"
    assert format_tl(Decimal("-450")) == "-450,00 ₺"


def test_format_tl_rejects_non_decimal_values() -> None:
    with pytest.raises(TypeError):
        format_tl(1250.50)  # type: ignore[arg-type]


def test_format_tr_date_converts_utc_to_istanbul_date() -> None:
    value = datetime(2026, 5, 12, 22, 30, tzinfo=UTC)

    assert format_tr_date(value) == "13.05.2026"


def test_format_tr_date_accepts_plain_date() -> None:
    assert format_tr_date(date(2026, 5, 12)) == "12.05.2026"
