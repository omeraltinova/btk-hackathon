"""Age helpers derived from birth dates."""

from __future__ import annotations

from datetime import date
from typing import Literal

AgeStatus = Literal["minor", "adult"]


def calculate_age(birth_date: date | None, *, today: date | None = None) -> int | None:
    """Return full years elapsed since birth date, or None when unknown."""
    if birth_date is None:
        return None
    current = today or date.today()
    years = current.year - birth_date.year
    if (current.month, current.day) < (birth_date.month, birth_date.day):
        years -= 1
    return max(years, 0)


def age_status(birth_date: date | None, *, today: date | None = None) -> AgeStatus | None:
    """Return legal age bucket from birth date."""
    age = calculate_age(birth_date, today=today)
    if age is None:
        return None
    return "minor" if age < 18 else "adult"
