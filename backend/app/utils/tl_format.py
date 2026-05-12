"""Turkish lira amount formatting helpers (master_plan §6)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

KURUS = Decimal("0.01")


def _group_thousands(value: str) -> str:
    groups: list[str] = []
    remaining = value
    while len(remaining) > 3:
        groups.append(remaining[-3:])
        remaining = remaining[:-3]
    groups.append(remaining)
    return ".".join(reversed(groups))


def format_tl(amount: Decimal) -> str:
    """Render `amount` as `1.250,50 ₺`.

    The project stores money as `Decimal`; accepting floats here would hide a
    precision bug at the formatting boundary.
    """
    if not isinstance(amount, Decimal):
        raise TypeError("format_tl expects Decimal, not float/int.")

    quantized = amount.quantize(KURUS, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    whole, fraction = f"{abs(quantized):.2f}".split(".")
    return f"{sign}{_group_thousands(whole)},{fraction} ₺"
