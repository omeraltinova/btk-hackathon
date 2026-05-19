"""Data export router — P6 (data ownership) implementation.

Returns a single ZIP containing three CSVs scoped to `visible_user_ids` so
parent accounts see the whole family, children/individuals see only their own
rows.  All CSVs are UTF-8 with a BOM byte sequence so Excel renders Turkish
characters correctly without manual import.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.category import Category
from app.models.saving_goal import SavingGoal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.utils.recurrence import recurrence_label

router = APIRouter(prefix="/api/exports", tags=["exports"])

ISTANBUL = ZoneInfo("Europe/Istanbul")
UTF8_BOM = "﻿"

TRANSACTION_TYPE_TR = {"income": "Gelir", "expense": "Gider"}
SOURCE_TR = {"manual": "Manuel", "receipt_ocr": "Fiş", "recurring": "Tekrarlayan"}
GOAL_TYPE_TR = {"expense_reduction": "Tasarruf", "accumulation": "Birikim"}
GOAL_STATUS_TR = {"active": "Aktif", "completed": "Tamamlandı", "paused": "Duraklatıldı"}
BILLING_CYCLE_TR = {
    "weekly": "Haftalık",
    "monthly": "Aylık",
    "yearly": "Yıllık",
    "custom": "Özel",
}


def _format_local_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=ISTANBUL)
    return value.astimezone(ISTANBUL).strftime("%d.%m.%Y %H:%M")


def _format_local_date(value: date | datetime | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(ISTANBUL)
        return value.strftime("%d.%m.%Y")
    return value.strftime("%d.%m.%Y")


def _build_transactions_csv(
    transactions: Sequence[Transaction],
    user_names: dict[UUID, str],
    category_names: dict[UUID, str],
) -> str:
    buffer = io.StringIO()
    buffer.write(UTF8_BOM)
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Tarih",
            "Tür",
            "Tutar",
            "Kategori",
            "Satıcı",
            "Açıklama",
            "Kaynak",
            "Hesap Sahibi",
        ],
    )
    for transaction in transactions:
        writer.writerow(
            [
                _format_local_datetime(transaction.occurred_at),
                TRANSACTION_TYPE_TR.get(transaction.type, transaction.type),
                f"{transaction.amount:.2f}",
                category_names.get(transaction.category_id, "")
                if transaction.category_id is not None
                else "",
                transaction.merchant or "",
                transaction.description or "",
                SOURCE_TR.get(transaction.source, transaction.source),
                user_names.get(transaction.user_id, ""),
            ],
        )
    return buffer.getvalue()


def _format_recurrence(subscription: Subscription) -> str:
    if subscription.billing_cycle != "custom":
        return BILLING_CYCLE_TR.get(subscription.billing_cycle, subscription.billing_cycle)
    return recurrence_label(
        subscription.recurrence_interval,
        subscription.recurrence_unit,
        subscription.billing_cycle,
    )


def _build_subscriptions_csv(
    subscriptions: Sequence[Subscription],
    user_names: dict[UUID, str],
    category_names: dict[UUID, str],
) -> str:
    buffer = io.StringIO()
    buffer.write(UTF8_BOM)
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Ad",
            "Tür",
            "Kurum/Satıcı",
            "Tutar",
            "Yenilenme",
            "Sonraki Tarih",
            "Kategori",
            "Durum",
            "Hesap Sahibi",
        ],
    )
    for subscription in subscriptions:
        writer.writerow(
            [
                subscription.name,
                TRANSACTION_TYPE_TR.get(subscription.type, subscription.type),
                subscription.merchant or "",
                f"{subscription.amount:.2f}",
                _format_recurrence(subscription),
                _format_local_date(subscription.next_billing_date)
                if subscription.next_billing_date is not None
                else "",
                category_names.get(subscription.category_id, "")
                if subscription.category_id is not None
                else "",
                "Aktif" if subscription.is_active else "Pasif",
                user_names.get(subscription.user_id, ""),
            ],
        )
    return buffer.getvalue()


def _build_goals_csv(
    goals: Sequence[SavingGoal],
    user_names: dict[UUID, str],
    category_names: dict[UUID, str],
) -> str:
    buffer = io.StringIO()
    buffer.write(UTF8_BOM)
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Başlık",
            "Tür",
            "Kategori",
            "Başlangıç",
            "Hedef",
            "Mevcut",
            "Hedef Tarih",
            "Aylık Katkı",
            "Durum",
            "Hesap Sahibi",
        ],
    )
    for goal in goals:
        if goal.goal_type == "accumulation":
            target_value = (
                goal.target_amount if goal.target_amount is not None else goal.target_saving_amount
            )
        else:
            target_value = goal.target_spending_amount
        writer.writerow(
            [
                goal.title,
                GOAL_TYPE_TR.get(goal.goal_type, goal.goal_type),
                category_names.get(goal.category_id, "") if goal.category_id is not None else "",
                f"{goal.baseline_amount:.2f}",
                f"{target_value:.2f}",
                f"{goal.current_amount:.2f}",
                _format_local_date(goal.end_date),
                f"{goal.monthly_contribution:.2f}" if goal.monthly_contribution is not None else "",
                GOAL_STATUS_TR.get(goal.status, goal.status),
                user_names.get(goal.user_id, ""),
            ],
        )
    return buffer.getvalue()


@router.get("/all.zip")
def export_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Download a ZIP containing the active scope's transactions, subscriptions, and goals."""
    user_ids = visible_user_ids(current_user)

    users = db.execute(select(User).where(User.id.in_(user_ids))).scalars().all()
    user_names = {user.id: user.name for user in users}

    categories = (
        db.execute(
            select(Category).where(or_(Category.user_id.in_(user_ids), Category.user_id.is_(None))),
        )
        .scalars()
        .all()
    )
    category_names = {category.id: category.name for category in categories}

    transactions = (
        db.execute(
            select(Transaction)
            .where(Transaction.user_id.in_(user_ids))
            .order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc()),
        )
        .scalars()
        .all()
    )
    subscriptions = (
        db.execute(
            select(Subscription)
            .where(Subscription.user_id.in_(user_ids))
            .order_by(Subscription.is_active.desc(), Subscription.name.asc()),
        )
        .scalars()
        .all()
    )
    goals = (
        db.execute(
            select(SavingGoal)
            .where(SavingGoal.user_id.in_(user_ids))
            .order_by(SavingGoal.status.asc(), SavingGoal.title.asc()),
        )
        .scalars()
        .all()
    )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "islemler.csv",
            _build_transactions_csv(transactions, user_names, category_names),
        )
        archive.writestr(
            "abonelikler.csv",
            _build_subscriptions_csv(subscriptions, user_names, category_names),
        )
        archive.writestr(
            "hedefler.csv",
            _build_goals_csv(goals, user_names, category_names),
        )

    today = datetime.now(ISTANBUL).strftime("%Y%m%d")
    filename = f"cuzdan-kocu-verim-{today}.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
