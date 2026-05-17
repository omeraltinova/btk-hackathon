"""Tests for the ZIP export router."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.models.category import Category
from app.models.saving_goal import SavingGoal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.routers.exports import UTF8_BOM, export_all

EntityList = list[Any]


class FakeScalars:
    def __init__(self, items: EntityList) -> None:
        self._items = items

    def all(self) -> EntityList:
        return self._items

    def __iter__(self):
        return iter(self._items)


class FakeResult:
    def __init__(self, items: EntityList) -> None:
        self._items = items

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._items)


class FakeSession:
    """Minimal in-memory session matching the queries `export_all` issues.

    Each `execute` call looks at the first column description to pick the
    entity, then filters by the `user_id`/`id` IN-clauses the router builds.
    """

    def __init__(
        self,
        *,
        users: EntityList,
        categories: EntityList,
        transactions: EntityList,
        subscriptions: EntityList,
        goals: EntityList,
    ) -> None:
        self.users = users
        self.categories = categories
        self.transactions = transactions
        self.subscriptions = subscriptions
        self.goals = goals

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        scope = self._scope_user_ids(statement)
        category_scope_includes_null = self._allows_null_category_user(statement)
        if entity is User:
            return FakeResult([user for user in self.users if user.id in scope])
        if entity is Category:
            items = [
                category
                for category in self.categories
                if category.user_id in scope
                or (category_scope_includes_null and category.user_id is None)
            ]
            return FakeResult(items)
        if entity is Transaction:
            return FakeResult([tx for tx in self.transactions if tx.user_id in scope])
        if entity is Subscription:
            return FakeResult([sub for sub in self.subscriptions if sub.user_id in scope])
        if entity is SavingGoal:
            return FakeResult([goal for goal in self.goals if goal.user_id in scope])
        return FakeResult([])

    @staticmethod
    def _scope_user_ids(statement: object) -> set[UUID]:
        """Pick up the UUID set used in the first `column.in_(...)` clause.

        Works regardless of whether the column is `user_id` (transactions etc.)
        or `id` (the user query), since `export_all` only uses one IN-clause
        per statement and both refer to user ids.
        """
        for criterion in getattr(statement, "_where_criteria", ()):
            for clause in getattr(criterion, "clauses", [criterion]):
                right = getattr(clause, "right", None)
                value = getattr(right, "value", None)
                if isinstance(value, list | tuple | set) and value:
                    return {UUID(str(v)) if not isinstance(v, UUID) else v for v in value}
        return set()

    @staticmethod
    def _allows_null_category_user(statement: object) -> bool:
        """Categories include `OR user_id IS NULL` for system defaults — detect that."""
        for criterion in getattr(statement, "_where_criteria", ()):
            text = str(criterion).lower()
            if "is null" in text and "user_id" in text:
                return True
        return False


def make_user(
    *,
    role: str = "individual",
    family_id: UUID | None = None,
    parent_id: UUID | None = None,
    name: str = "Test Kullanıcı",
) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        name=name,
        role=role,
        parent_id=parent_id,
        password_hash="hash",
        family_id=family_id,
        birth_date=date(1991, 1, 1) if role != "child" else date(2014, 1, 1),
        finance_level="beginner" if role != "child" else "child",
        is_demo=False,
    )
    user.children = []
    return user


def make_transaction(
    user_id: UUID,
    *,
    amount: str = "120.50",
    category_id: UUID | None = None,
    merchant: str = "Migros",
    tx_type: str = "expense",
    description: str = "Market",
) -> Transaction:
    return Transaction(
        id=uuid4(),
        user_id=user_id,
        amount=Decimal(amount),
        type=tx_type,
        category_id=category_id,
        description=description,
        merchant=merchant,
        occurred_at=datetime(2026, 5, 10, 14, 30, tzinfo=UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )


def make_subscription(
    user_id: UUID, *, name: str = "Netflix", category_id: UUID | None = None
) -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user_id,
        name=name,
        merchant="Netflix Türkiye",
        amount=Decimal("149.99"),
        type="expense",
        billing_cycle="monthly",
        recurrence_interval=1,
        recurrence_unit="month",
        next_billing_date=date(2026, 6, 1),
        category_id=category_id,
        is_active=True,
        detected_from_transactions=False,
        usage_score=None,
    )


def make_goal(
    user_id: UUID, *, title: str = "Tatil için birikim", category_id: UUID | None = None
) -> SavingGoal:
    return SavingGoal(
        id=uuid4(),
        user_id=user_id,
        category_id=category_id,
        goal_type="accumulation",
        title=title,
        baseline_amount=Decimal("0"),
        target_spending_amount=Decimal("0"),
        target_saving_amount=Decimal("5000"),
        target_amount=Decimal("5000"),
        current_amount=Decimal("1200"),
        monthly_contribution=Decimal("400"),
        start_date=datetime(2026, 5, 1, tzinfo=UTC),
        end_date=datetime(2026, 12, 1, tzinfo=UTC),
        status="active",
        strategy=None,
        created_by="manual",
    )


def _read_zip(response: Any) -> dict[str, str]:
    buffer = io.BytesIO(response.body)
    with zipfile.ZipFile(buffer, "r") as archive:
        return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}


def _csv_rows(content: str) -> list[list[str]]:
    assert content.startswith(UTF8_BOM), "CSV must start with a UTF-8 BOM for Excel"
    stripped = content[len(UTF8_BOM) :]
    return list(csv.reader(io.StringIO(stripped)))


def test_export_all_returns_three_csvs_with_bom_and_turkish_headers() -> None:
    individual = make_user(role="individual", name="Kerem Yeni")
    transaction = make_transaction(individual.id)
    subscription = make_subscription(individual.id)
    goal = make_goal(individual.id)
    db = FakeSession(
        users=[individual],
        categories=[],
        transactions=[transaction],
        subscriptions=[subscription],
        goals=[goal],
    )

    response = export_all(db=db, current_user=individual)  # type: ignore[arg-type]

    assert response.media_type == "application/zip"
    disposition = response.headers["content-disposition"]
    assert "cuzdan-kocu-verim-" in disposition
    assert disposition.endswith('.zip"')

    files = _read_zip(response)
    assert set(files) == {"islemler.csv", "abonelikler.csv", "hedefler.csv"}

    transactions_rows = _csv_rows(files["islemler.csv"])
    assert transactions_rows[0] == [
        "Tarih",
        "Tür",
        "Tutar",
        "Kategori",
        "Satıcı",
        "Açıklama",
        "Kaynak",
        "Hesap Sahibi",
    ]
    assert transactions_rows[1][1] == "Gider"
    assert transactions_rows[1][2] == "120.50"
    assert transactions_rows[1][6] == "Manuel"
    assert transactions_rows[1][7] == "Kerem Yeni"

    subscription_rows = _csv_rows(files["abonelikler.csv"])
    assert subscription_rows[0] == [
        "Ad",
        "Tür",
        "Kurum/Satıcı",
        "Tutar",
        "Yenilenme",
        "Sonraki Tarih",
        "Kategori",
        "Durum",
        "Hesap Sahibi",
    ]
    assert subscription_rows[1][4] == "Aylık"
    assert subscription_rows[1][7] == "Aktif"

    goals_rows = _csv_rows(files["hedefler.csv"])
    assert goals_rows[0] == [
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
    ]
    assert goals_rows[1][1] == "Birikim"
    assert goals_rows[1][8] == "Aktif"


def test_export_all_parent_sees_family_records() -> None:
    family_id = uuid4()
    parent = make_user(role="parent", family_id=family_id, name="Ayşe Yılmaz")
    child = make_user(role="child", family_id=family_id, parent_id=parent.id, name="Elif Yılmaz")
    stranger = make_user(role="individual", name="Yabancı")
    parent.children = [child]

    db = FakeSession(
        users=[parent, child, stranger],
        categories=[],
        transactions=[
            make_transaction(parent.id, merchant="Migros"),
            make_transaction(child.id, merchant="Okul kantini", description="Tost"),
            make_transaction(stranger.id, merchant="Yabancı işlemi"),
        ],
        subscriptions=[],
        goals=[],
    )

    response = export_all(db=db, current_user=parent)  # type: ignore[arg-type]
    files = _read_zip(response)
    rows = _csv_rows(files["islemler.csv"])
    merchants = {row[4] for row in rows[1:]}
    assert "Migros" in merchants
    assert "Okul kantini" in merchants
    assert "Yabancı işlemi" not in merchants


def test_export_all_child_only_sees_own_records() -> None:
    family_id = uuid4()
    parent = make_user(role="parent", family_id=family_id)
    child = make_user(role="child", family_id=family_id, parent_id=parent.id, name="Elif")
    parent.children = [child]

    db = FakeSession(
        users=[parent, child],
        categories=[],
        transactions=[
            make_transaction(parent.id, merchant="Migros"),
            make_transaction(child.id, merchant="Okul"),
        ],
        subscriptions=[],
        goals=[],
    )

    response = export_all(db=db, current_user=child)  # type: ignore[arg-type]
    files = _read_zip(response)
    rows = _csv_rows(files["islemler.csv"])
    assert len(rows) == 2  # header + 1 row
    assert rows[1][4] == "Okul"
    assert rows[1][7] == "Elif"
