"""Shared data structures for generated monthly reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class ReportCategoryTotal:
    category_name: str
    amount: Decimal
    share_percent: Decimal
    transaction_count: int


@dataclass(frozen=True)
class ReportMemberSummary:
    user_id: UUID
    name: str
    role: str
    age_status: str | None
    income: Decimal
    expense: Decimal
    balance: Decimal
    transaction_count: int


@dataclass(frozen=True)
class ReportGoalSummary:
    title: str
    goal_type: str
    progress_percent: Decimal
    current_amount: Decimal
    target_amount: Decimal
    remaining_amount: Decimal
    status_label: str


@dataclass(frozen=True)
class ReportSubscriptionSummary:
    name: str
    type: str
    monthly_equivalent: Decimal
    next_billing_date: str | None


@dataclass(frozen=True)
class ReportEnvelopeSummary:
    label: str
    budget: Decimal
    spent: Decimal
    remaining: Decimal
    used_percent: Decimal | None
    status: str
    safe_daily_amount: Decimal
    days_left_in_month: int


@dataclass(frozen=True)
class ReportImage:
    title: str
    description: str
    content: bytes


@dataclass(frozen=True)
class MonthlyReportData:
    owner_user_id: UUID
    owner_name: str
    owner_role: str
    owner_finance_level: str
    scope_type: str
    title: str
    period_start: datetime
    period_end: datetime
    previous_period_start: datetime
    previous_period_end: datetime
    included_user_ids: list[UUID]
    included_names: list[str]
    total_income: Decimal
    total_expense: Decimal
    total_balance: Decimal
    previous_income: Decimal
    previous_expense: Decimal
    category_totals: list[ReportCategoryTotal]
    envelope_summaries: list[ReportEnvelopeSummary]
    members: list[ReportMemberSummary]
    goal_summaries: list[ReportGoalSummary]
    subscriptions: list[ReportSubscriptionSummary]
    recurring_income_monthly: Decimal
    recurring_expense_monthly: Decimal
    budgeted_month: Decimal
    remaining_budget: Decimal
    assessment: str
    suggestions: list[str]
