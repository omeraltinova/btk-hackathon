from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.agent.tools import (
    build_spending_summary,
    build_subscriptions_summary,
    build_user_memory,
    infer_category_from_text,
)
from app.models.category import Category
from app.models.memory import AgentMemory
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User


class FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalar_one_or_none(self) -> Any | None:
        return self._items[0] if self._items else None

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._items)


class FakeSession:
    def __init__(
        self,
        *,
        categories: list[Category] | None = None,
        transactions: list[Transaction] | None = None,
        subscriptions: list[Subscription] | None = None,
        memories: list[AgentMemory] | None = None,
    ) -> None:
        self.categories = categories or []
        self.transactions = transactions or []
        self.subscriptions = subscriptions or []
        self.memories = memories or []

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is Category:
            return FakeResult(self.categories)
        if entity is Transaction:
            return FakeResult(
                [item for item in self.transactions if self._matches_statement(statement, item)],
            )
        if entity is Subscription:
            return FakeResult(
                [item for item in self.subscriptions if self._matches_statement(statement, item)],
            )
        if entity is AgentMemory:
            return FakeResult(
                [item for item in self.memories if self._matches_statement(statement, item)],
            )
        return FakeResult([])

    def _matches_statement(self, statement: object, row: object) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "user_id" and not self._matches_user_id(value, row):
                return False
            if column_name == "type" and getattr(row, "type", None) != value:
                return False
            if column_name == "occurred_at" and getattr(row, "occurred_at") < value:
                return False
            if column_name == "is_active":
                requested = value if value is not None else str(getattr(criterion, "right", ""))
                if bool(getattr(row, "is_active")) != (requested is True or requested == "true"):
                    return False
            if column_name == "key" and getattr(row, "key") != value:
                return False
        return True

    @staticmethod
    def _matches_user_id(value: object, row: object) -> bool:
        user_id = getattr(row, "user_id")
        if isinstance(value, list | tuple | set):
            return user_id in value
        return user_id == value


def make_user(*, role: str = "individual", parent_id: UUID | None = None) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        name="Test Kullanıcı",
        role=role,
        parent_id=parent_id,
        password_hash="hash",
        birth_date=date(1991, 1, 1),
        finance_level="beginner",
        is_demo=False,
    )
    user.children = []
    return user


def make_category(name: str) -> Category:
    return Category(
        id=uuid4(),
        user_id=None,
        name=name,
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )


def make_transaction(
    *,
    user_id: UUID,
    category_id: UUID | None,
    amount: str,
    tx_type: str = "expense",
) -> Transaction:
    return Transaction(
        id=uuid4(),
        user_id=user_id,
        amount=Decimal(amount),
        type=tx_type,
        category_id=category_id,
        description=None,
        merchant="Market",
        occurred_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )


def make_subscription(
    *,
    user_id: UUID,
    amount: str,
    cycle: str = "monthly",
    is_active: bool = True,
) -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user_id,
        name="Dijital servis",
        merchant="Servis",
        amount=Decimal(amount),
        billing_cycle=cycle,
        recurrence_interval=1,
        recurrence_unit={"weekly": "week", "yearly": "year"}.get(cycle, "month"),
        next_billing_date=date(2026, 6, 1),
        category_id=None,
        is_active=is_active,
        detected_from_transactions=False,
        usage_score=Decimal("0.50"),
    )


def test_build_spending_summary_uses_parent_visible_scope_and_decimal_format() -> None:
    parent = make_user(role="parent")
    child = make_user(role="child", parent_id=parent.id)
    other = make_user()
    parent.children = [child]
    market = make_category("Market")
    db = FakeSession(
        categories=[market],
        transactions=[
            make_transaction(user_id=parent.id, category_id=market.id, amount="100.00"),
            make_transaction(user_id=child.id, category_id=market.id, amount="75.25"),
            make_transaction(user_id=other.id, category_id=market.id, amount="999.00"),
            make_transaction(
                user_id=parent.id,
                category_id=market.id,
                amount="4000.00",
                tx_type="income",
            ),
        ],
    )

    result = build_spending_summary(
        db, parent, category="Market", now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    )

    assert result["transaction_count"] == 2
    assert result["total_amount"] == "175.25"
    assert result["total_amount_formatted"] == "175,25 ₺"


def test_build_subscriptions_summary_filters_active_and_calculates_monthly_total() -> None:
    user = make_user()
    other = make_user()
    db = FakeSession(
        subscriptions=[
            make_subscription(user_id=user.id, amount="120.00"),
            make_subscription(user_id=user.id, amount="25.00", cycle="weekly"),
            make_subscription(user_id=user.id, amount="300.00", is_active=False),
            make_subscription(user_id=other.id, amount="999.00"),
        ],
    )

    result = build_subscriptions_summary(db, user)

    assert result["count"] == 2
    assert result["monthly_total"] == "220.00"
    assert result["monthly_total_formatted"] == "220,00 ₺"


def test_build_user_memory_reads_current_user_only() -> None:
    user = make_user()
    other = make_user()
    db = FakeSession(
        memories=[
            AgentMemory(id=uuid4(), user_id=user.id, key="hedef", value={"text": "birikim"}),
            AgentMemory(id=uuid4(), user_id=other.id, key="hedef", value={"text": "başka"}),
        ],
    )

    result = build_user_memory(db, user, key="hedef")

    assert result["count"] == 1
    assert result["entries"] == [{"key": "hedef", "value": {"text": "birikim"}}]


def test_infer_category_from_text_matches_turkish_suffixes() -> None:
    user = make_user()
    db = FakeSession(categories=[make_category("Market"), make_category("Fatura")])

    assert infer_category_from_text(db, user, "Bu ay markete ne kadar harcadım?") == "Market"
