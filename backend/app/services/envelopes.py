"""Envelope budget helpers shared by dashboard and agent tools."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.models.category import Category

ISTANBUL = ZoneInfo("Europe/Istanbul")
MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.1")


@dataclass(frozen=True)
class EnvelopeDefinition:
    slug: str
    label: str
    category_name: str
    category_aliases: tuple[str, ...]
    text_aliases: tuple[str, ...]
    is_savings_goal: bool = False


@dataclass(frozen=True)
class BudgetEnvelope:
    slug: str
    label: str
    category_name: str
    budget: Decimal
    spent: Decimal
    remaining: Decimal
    days_left_in_month: int
    safe_daily_amount: Decimal
    used_percent: Decimal | None
    status: str
    is_savings_goal: bool
    is_custom: bool = False


@dataclass(frozen=True)
class RiskyCategory:
    slug: str
    label: str
    category_name: str
    budget: Decimal
    spent: Decimal
    remaining: Decimal
    used_percent: Decimal


@dataclass(frozen=True)
class EnvelopeBudgetSummary:
    budgeted_month: Decimal
    spent_month: Decimal
    remaining_budget: Decimal
    risky_category: RiskyCategory | None
    envelopes: list[BudgetEnvelope]


ENVELOPE_DEFINITIONS: tuple[EnvelopeDefinition, ...] = (
    EnvelopeDefinition(
        slug="market",
        label="Market zarfı",
        category_name="Market",
        category_aliases=("Market",),
        text_aliases=("market", "market zarfi"),
    ),
    EnvelopeDefinition(
        slug="fatura",
        label="Fatura zarfı",
        category_name="Fatura",
        category_aliases=("Fatura",),
        text_aliases=("fatura", "fatura zarfi"),
    ),
    EnvelopeDefinition(
        slug="okul",
        label="Okul zarfı",
        category_name="Eğitim",
        category_aliases=("Eğitim", "Okul"),
        text_aliases=("okul", "okul zarfi", "egitim", "egitim zarfi"),
    ),
    EnvelopeDefinition(
        slug="ulasim",
        label="Ulaşım zarfı",
        category_name="Ulaşım",
        category_aliases=("Ulaşım", "Ulasim"),
        text_aliases=("ulasim", "ulasim zarfi", "ulaşim", "ulaşim zarfi"),
    ),
    EnvelopeDefinition(
        slug="harclik",
        label="Harçlık zarfı",
        category_name="Harçlık",
        category_aliases=("Harçlık", "Harclik"),
        text_aliases=("harclik", "harclik zarfi", "harçlık", "harçlık zarfı"),
    ),
    EnvelopeDefinition(
        slug="birikim",
        label="Birikim zarfı",
        category_name="Birikim",
        category_aliases=("Birikim",),
        text_aliases=("birikim", "birikim zarfi", "birikim hedefi"),
        is_savings_goal=True,
    ),
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _fold(value: str) -> str:
    return (
        value.casefold()
        .replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )


def _days_left_in_month(value: datetime) -> int:
    local = value.astimezone(ISTANBUL)
    last_day = monthrange(local.year, local.month)[1]
    return max(0, last_day - local.day)


def _category_matches(definition: EnvelopeDefinition, category: Category) -> bool:
    aliases = {_fold(alias) for alias in definition.category_aliases}
    return _fold(category.name) in aliases


def envelope_definition_for_slug(slug: str) -> EnvelopeDefinition | None:
    folded = _fold(slug)
    for definition in ENVELOPE_DEFINITIONS:
        if _fold(definition.slug) == folded:
            return definition
    return None


def envelope_definition_for_category_name(name: str) -> EnvelopeDefinition | None:
    folded = _fold(name)
    for definition in ENVELOPE_DEFINITIONS:
        aliases = {_fold(alias) for alias in definition.category_aliases}
        if folded in aliases:
            return definition
    return None


def custom_envelope_slug(category: Category) -> str:
    return f"custom-{category.id}"


def custom_envelope_category_id(slug: str) -> UUID | None:
    prefix = "custom-"
    if not slug.startswith(prefix):
        return None
    try:
        return UUID(slug.removeprefix(prefix))
    except ValueError:
        return None


def category_matches_envelope(definition: EnvelopeDefinition, category: Category) -> bool:
    return _category_matches(definition, category)


def _budget_for_matches(categories: list[Category]) -> Decimal:
    owned_budgets = [
        category.budget_monthly
        for category in categories
        if category.user_id is not None and category.budget_monthly is not None
    ]
    if owned_budgets:
        return _money(
            sum(
                (Decimal(budget) for budget in owned_budgets),
                Decimal("0"),
            ),
        )

    system_budget = sum(
        (
            Decimal(budget)
            for category in categories
            if category.user_id is None
            for budget in [category.budget_monthly]
            if budget is not None
        ),
        Decimal("0"),
    )
    return _money(system_budget)


def resolve_envelope_category(text: str) -> str | None:
    """Return the canonical category name if `text` references a zarf."""
    folded = _fold(text)
    for definition in ENVELOPE_DEFINITIONS:
        if any(_fold(alias) in folded for alias in definition.text_aliases):
            return definition.category_name
    return None


def build_envelope_budget_summary(
    *,
    categories: list[Category],
    current_category_totals: dict[UUID | None, Decimal],
    now: datetime | None = None,
) -> EnvelopeBudgetSummary:
    period_end = now or datetime.now(UTC)
    if period_end.tzinfo is None or period_end.utcoffset() is None:
        period_end = period_end.replace(tzinfo=UTC)
    days_left = _days_left_in_month(period_end)
    envelopes: list[BudgetEnvelope] = []
    matched_category_ids: set[UUID] = set()

    for definition in ENVELOPE_DEFINITIONS:
        matching_categories = [
            category for category in categories if _category_matches(definition, category)
        ]
        matching_category_ids = {category.id for category in matching_categories}
        matched_category_ids.update(matching_category_ids)
        spent = _money(
            sum(
                (
                    current_category_totals.get(category_id, Decimal("0"))
                    for category_id in matching_category_ids
                ),
                Decimal("0"),
            ),
        )
        budget = _budget_for_matches(matching_categories)
        remaining = _money(budget - spent)
        safe_daily = (
            _money(remaining / Decimal(days_left))
            if remaining > 0 and days_left > 0
            else Decimal("0.00")
        )
        used_percent = (
            ((spent / budget) * Decimal("100")).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)
            if budget > 0
            else None
        )
        status = "safe"
        if definition.is_savings_goal:
            status = "safe"
        elif budget > 0 and spent > budget:
            status = "over"
        elif used_percent is not None and used_percent >= Decimal("80.0"):
            status = "watch"

        envelopes.append(
            BudgetEnvelope(
                slug=definition.slug,
                label=definition.label,
                category_name=definition.category_name,
                budget=budget,
                spent=spent,
                remaining=remaining,
                days_left_in_month=days_left,
                safe_daily_amount=safe_daily,
                used_percent=used_percent,
                status=status,
                is_savings_goal=definition.is_savings_goal,
            ),
        )

    for category in categories:
        if category.id in matched_category_ids:
            continue
        if category.user_id is None or category.budget_monthly is None:
            continue
        if Decimal(category.budget_monthly) <= 0:
            continue

        spent = _money(current_category_totals.get(category.id, Decimal("0")))
        budget = _money(Decimal(category.budget_monthly))
        remaining = _money(budget - spent)
        safe_daily = (
            _money(remaining / Decimal(days_left))
            if remaining > 0 and days_left > 0
            else Decimal("0.00")
        )
        used_percent = (
            ((spent / budget) * Decimal("100")).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)
            if budget > 0
            else None
        )
        status = "safe"
        if budget > 0 and spent > budget:
            status = "over"
        elif used_percent is not None and used_percent >= Decimal("80.0"):
            status = "watch"

        envelopes.append(
            BudgetEnvelope(
                slug=custom_envelope_slug(category),
                label=f"{category.name} zarfı",
                category_name=category.name,
                budget=budget,
                spent=spent,
                remaining=remaining,
                days_left_in_month=days_left,
                safe_daily_amount=safe_daily,
                used_percent=used_percent,
                status=status,
                is_savings_goal=False,
                is_custom=True,
            ),
        )

    risky_candidates = [
        envelope
        for envelope in envelopes
        if not envelope.is_savings_goal
        and envelope.used_percent is not None
        and envelope.used_percent >= Decimal("80.0")
    ]
    risky_envelope = max(
        risky_candidates, key=lambda item: item.used_percent or Decimal("0"), default=None
    )
    risky_category = (
        RiskyCategory(
            slug=risky_envelope.slug,
            label=risky_envelope.label,
            category_name=risky_envelope.category_name,
            budget=risky_envelope.budget,
            spent=risky_envelope.spent,
            remaining=risky_envelope.remaining,
            used_percent=risky_envelope.used_percent or Decimal("0"),
        )
        if risky_envelope is not None
        else None
    )

    budgeted_month = _money(sum((item.budget for item in envelopes), Decimal("0")))
    spent_month = _money(sum((item.spent for item in envelopes), Decimal("0")))
    return EnvelopeBudgetSummary(
        budgeted_month=budgeted_month,
        spent_month=spent_month,
        remaining_budget=_money(budgeted_month - spent_month),
        risky_category=risky_category,
        envelopes=envelopes,
    )
