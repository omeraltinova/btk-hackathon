"""Turkish lira amount formatting helpers (master_plan §6).

Stub: real implementation arrives on Day 2 alongside the first money-rendering
endpoint. Keeping it here so imports don't break and so the contract is
visible: `Decimal` in, `str` out — never `float`.
"""

from __future__ import annotations

from decimal import Decimal


def format_tl(amount: Decimal) -> str:
    """Render `amount` as `1.250,50 ₺`. Implementation Day 2."""
    raise NotImplementedError("Day 2 — see docs/master_plan.md §6 for spec.")
