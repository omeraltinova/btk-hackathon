"""Recurring interval helpers for subscriptions."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

RecurrenceUnit = Literal["day", "week", "month", "year"]

MONEY_QUANT = Decimal("0.01")


def recurrence_from_billing_cycle(billing_cycle: str) -> tuple[int, RecurrenceUnit]:
    if billing_cycle == "weekly":
        return 1, "week"
    if billing_cycle == "yearly":
        return 1, "year"
    return 1, "month"


def monthly_equivalent(
    amount: Decimal,
    recurrence_interval: int | None,
    recurrence_unit: str | None,
    billing_cycle: str = "monthly",
) -> Decimal:
    interval = recurrence_interval or 1
    unit = recurrence_unit or recurrence_from_billing_cycle(billing_cycle)[1]
    if interval < 1:
        interval = 1
    if unit == "day":
        monthly = amount * (Decimal("30") / Decimal(interval))
    elif unit == "week":
        monthly = amount * (Decimal("4") / Decimal(interval))
    elif unit == "year":
        monthly = amount / (Decimal("12") * Decimal(interval))
    else:
        monthly = amount / Decimal(interval)
    return monthly.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def recurrence_label(interval: int | None, unit: str | None, billing_cycle: str = "monthly") -> str:
    safe_interval = interval or 1
    safe_unit = unit or recurrence_from_billing_cycle(billing_cycle)[1]
    if safe_interval <= 1:
        return {
            "day": "Her gün",
            "week": "Haftada bir",
            "month": "Ayda bir",
            "year": "Yılda bir",
        }.get(safe_unit, "Ayda bir")
    suffix = {
        "day": "günde",
        "week": "haftada",
        "month": "ayda",
        "year": "yılda",
    }.get(safe_unit, "ayda")
    return f"Her {safe_interval} {suffix} bir"
