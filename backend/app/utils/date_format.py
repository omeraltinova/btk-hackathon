"""Turkish date formatting helpers (master_plan §6)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

ISTANBUL = ZoneInfo("Europe/Istanbul")


def format_tr_date(value: date | datetime) -> str:
    """Render a date/datetime as `gg.aa.yyyy` in Europe/Istanbul."""
    if isinstance(value, datetime):
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
        local = aware.astimezone(ISTANBUL)
        return local.strftime("%d.%m.%Y")
    return value.strftime("%d.%m.%Y")
