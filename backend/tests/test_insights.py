from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.models.category import Category
from app.models.insight import ProactiveInsight
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.services.insights import build_insight_candidates, refresh_insights_for_user


class FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._items)


class FakeSession:
    def __init__(
        self,
        *,
        categories: list[Category] | None = None,
        transactions: list[Transaction] | None = None,
        subscriptions: list[Subscription] | None = None,
        insights: list[ProactiveInsight] | None = None,
    ) -> None:
        self.categories = categories or []
        self.transactions = transactions or []
        self.subscriptions = subscriptions or []
        self.insights = insights or []

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
        if entity is ProactiveInsight:
            return FakeResult(
                [item for item in self.insights if self._matches_statement(statement, item)],
            )
        return FakeResult([])

    def add_all(self, items: list[ProactiveInsight]) -> None:
        for item in items:
            if item.id is None:
                item.id = uuid4()
            if getattr(item, "created_at", None) is None:
                item.created_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
            if getattr(item, "updated_at", None) is None:
                item.updated_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
            self.insights.append(item)

    def commit(self) -> None:
        return None

    def refresh(self, item: ProactiveInsight) -> None:
        if item.id is None:
            item.id = uuid4()
        if getattr(item, "created_at", None) is None:
            item.created_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
        if getattr(item, "updated_at", None) is None:
            item.updated_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)

    def _matches_statement(self, statement: object, row: object) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "user_id" and not self._matches_user_id(value, row):
                return False
            if column_name == "occurred_at" and getattr(row, "occurred_at") < value:
                return False
            if column_name == "is_active":
                requested = value if value is not None else str(getattr(criterion, "right", ""))
                if bool(getattr(row, "is_active")) != (requested is True or requested == "true"):
                    return False
            if column_name == "is_dismissed":
                requested = value if value is not None else str(getattr(criterion, "right", ""))
                if bool(getattr(row, "is_dismissed")) != (requested is True or requested == "true"):
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
        age=35,
        finance_level="beginner",
        is_demo=False,
    )
    user.children = []
    return user


def make_category(*, name: str, budget: str | None = None) -> Category:
    return Category(
        id=uuid4(),
        user_id=None,
        name=name,
        icon=None,
        parent_id=None,
        budget_monthly=Decimal(budget) if budget else None,
    )


def make_transaction(
    *,
    user_id: UUID,
    category_id: UUID | None,
    amount: str,
    occurred_at: datetime,
    tx_type: str = "expense",
    source: str = "manual",
) -> Transaction:
    return Transaction(
        id=uuid4(),
        user_id=user_id,
        amount=Decimal(amount),
        type=tx_type,
        category_id=category_id,
        description=None,
        merchant="Market",
        occurred_at=occurred_at,
        source=source,
        receipt_image_url=None,
        raw_ocr_data=None,
    )


def make_subscription(*, user_id: UUID, amount: str, next_date: date) -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user_id,
        name="İnternet faturası",
        merchant="Servis",
        amount=Decimal(amount),
        billing_cycle="monthly",
        next_billing_date=next_date,
        category_id=None,
        is_active=True,
        detected_from_transactions=False,
        usage_score=Decimal("0.60"),
    )


def test_build_insight_candidates_generates_financial_rules() -> None:
    user = make_user()
    market = make_category(name="Market", budget="200.00")
    db = FakeSession(
        categories=[market],
        transactions=[
            make_transaction(
                user_id=user.id,
                category_id=market.id,
                amount="100.00",
                occurred_at=datetime(2026, 4, 10, 9, 0, tzinfo=UTC),
            ),
            make_transaction(
                user_id=user.id,
                category_id=market.id,
                amount="260.00",
                occurred_at=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
                source="receipt_ocr",
            ),
            make_transaction(
                user_id=user.id,
                category_id=None,
                amount="1000.00",
                occurred_at=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
                tx_type="income",
            ),
        ],
        subscriptions=[
            make_subscription(user_id=user.id, amount="120.00", next_date=date(2026, 5, 15)),
        ],
    )

    candidates = build_insight_candidates(db, user, now=datetime(2026, 5, 12, 12, 0, tzinfo=UTC))
    insight_types = {candidate.insight_type for candidate in candidates}

    assert "monthly_status" in insight_types
    assert "spending_spike" in insight_types
    assert "category_overspending" in insight_types
    assert "upcoming_recurring" in insight_types
    assert "receipt_activity" in insight_types


def test_refresh_insights_dismisses_old_active_items_and_persists_new_ones() -> None:
    user = make_user()
    old = ProactiveInsight(
        id=uuid4(),
        user_id=user.id,
        insight_type="monthly_status",
        title="Eski not",
        content="Eski içerik",
        severity="info",
        action_label=None,
        is_dismissed=False,
    )
    old.created_at = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    old.updated_at = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    db = FakeSession(insights=[old])

    refreshed = refresh_insights_for_user(
        db,
        user,
        now=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
    )

    assert old.is_dismissed is True
    assert len(refreshed) == 1
    assert refreshed[0].insight_type == "low_activity"
    assert refreshed[0] in db.insights
