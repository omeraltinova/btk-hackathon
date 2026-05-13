from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.agent.tools import (
    build_concept_illustration,
    build_saving_goal_creation,
    build_saving_goal_progress,
    build_smart_saving_plan,
    build_spending_chart,
    build_spending_summary,
    build_subscriptions_summary,
    build_user_memory,
    infer_category_from_text,
)
from app.models.category import Category
from app.models.memory import AgentMemory
from app.models.saving_goal import SavingGoal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.services.envelopes import build_envelope_budget_summary


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
        saving_goals: list[SavingGoal] | None = None,
    ) -> None:
        self.categories = categories or []
        self.transactions = transactions or []
        self.subscriptions = subscriptions or []
        self.memories = memories or []
        self.saving_goals = saving_goals or []

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
        if entity is SavingGoal:
            return FakeResult(
                [item for item in self.saving_goals if self._matches_statement(statement, item)],
            )
        return FakeResult([])

    def add(self, item: object) -> None:
        if isinstance(item, SavingGoal):
            if item.id is None:
                item.id = uuid4()
            self.saving_goals.append(item)

    def commit(self) -> None:
        return None

    def refresh(self, item: object) -> None:
        if isinstance(item, SavingGoal) and item.id is None:
            item.id = uuid4()

    def _matches_statement(self, statement: object, row: object) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "user_id" and not self._matches_user_id(value, row):
                return False
            if column_name == "category_id" and getattr(row, "category_id", None) != value:
                return False
            if column_name == "type" and getattr(row, "type", None) != value:
                return False
            if column_name == "status" and getattr(row, "status", None) != value:
                return False
            if column_name == "occurred_at":
                operator_name = getattr(getattr(criterion, "operator", None), "__name__", "")
                occurred_at = getattr(row, "occurred_at")
                if operator_name == "ge" and occurred_at < value:
                    return False
                if operator_name == "lt" and occurred_at >= value:
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


def make_category(name: str, *, budget: str | None = None) -> Category:
    return Category(
        id=uuid4(),
        user_id=None,
        name=name,
        icon=None,
        parent_id=None,
        budget_monthly=Decimal(budget) if budget is not None else None,
    )


def make_transaction(
    *,
    user_id: UUID,
    category_id: UUID | None,
    amount: str,
    tx_type: str = "expense",
    occurred_at: datetime = datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
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
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )


def make_saving_goal(
    *,
    user_id: UUID,
    category_id: UUID,
    baseline: str = "600.00",
    target: str = "510.00",
    saving: str = "90.00",
) -> SavingGoal:
    return SavingGoal(
        id=uuid4(),
        user_id=user_id,
        category_id=category_id,
        title="Market harcamamı azalt",
        baseline_amount=Decimal(baseline),
        target_spending_amount=Decimal(target),
        target_saving_amount=Decimal(saving),
        start_date=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        end_date=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
        status="active",
        strategy={"tactics": ["Haftalık üst limitini takip et."]},
        created_by="agent",
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


def test_build_spending_chart_returns_string_amounts_not_float() -> None:
    user = make_user()
    market = make_category("Market")
    db = FakeSession(
        categories=[market],
        transactions=[make_transaction(user_id=user.id, category_id=market.id, amount="100.25")],
    )

    result = build_spending_chart(db, user, now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC))
    chart = result["chart"]

    assert isinstance(chart, dict)
    data = chart["data"]
    assert isinstance(data, list)
    assert data[0]["value"] == "100.25"
    assert not isinstance(data[0]["value"], float)


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


def test_build_concept_illustration_rejects_investment_visuals() -> None:
    user = make_user()
    db = FakeSession()

    result = build_concept_illustration(db, user, concept="Hangi hisseyi alayım?")

    assert "error" in result
    assert result["concept"] == "Hangi hisseyi alayım?"


def test_infer_category_from_text_matches_turkish_suffixes() -> None:
    user = make_user()
    db = FakeSession(categories=[make_category("Market"), make_category("Fatura")])

    assert infer_category_from_text(db, user, "Bu ay markete ne kadar harcadım?") == "Market"


def test_build_spending_summary_includes_envelope_budget_details() -> None:
    user = make_user()
    market = make_category("Market", budget="600.00")
    db = FakeSession(
        categories=[market],
        transactions=[make_transaction(user_id=user.id, category_id=market.id, amount="180.00")],
    )

    result = build_spending_summary(
        db,
        user,
        category="market zarfı",
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert result["category"] == "Market"
    assert result["total_amount_formatted"] == "180,00 ₺"
    assert result["budget_envelope"] == {
        "slug": "market",
        "label": "Market zarfı",
        "category_name": "Market",
        "budget": "600.00",
        "budget_formatted": "600,00 ₺",
        "spent": "180.00",
        "spent_formatted": "180,00 ₺",
        "remaining": "420.00",
        "remaining_formatted": "420,00 ₺",
        "days_left_in_month": 18,
        "safe_daily_amount": "23.33",
        "safe_daily_amount_formatted": "23,33 ₺",
        "status": "safe",
        "is_savings_goal": False,
    }


def test_envelope_budget_summary_excludes_savings_goal_from_risky_category() -> None:
    market = make_category("Market", budget="100.00")
    savings = make_category("Birikim", budget="100.00")

    result = build_envelope_budget_summary(
        categories=[market, savings],
        current_category_totals={market.id: Decimal("90.00"), savings.id: Decimal("100.00")},
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert result.risky_category is not None
    assert result.risky_category.slug == "market"
    savings_envelope = next(envelope for envelope in result.envelopes if envelope.slug == "birikim")
    assert savings_envelope.status == "safe"


def test_build_saving_goal_creation_uses_decimal_category_spending() -> None:
    user = make_user()
    market = make_category("Market")
    db = FakeSession(
        categories=[market],
        transactions=[
            make_transaction(
                user_id=user.id,
                category_id=market.id,
                amount="600.00",
                occurred_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
            ),
        ],
    )

    result = build_saving_goal_creation(
        db,
        user,
        category="Market",
        target_reduction_percent=15,
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert result["created"] is True
    assert result["category_name"] == "Market"
    assert result["baseline_amount"] == "600.00"
    assert result["target_spending_amount"] == "510.00"
    assert result["target_saving_amount_formatted"] == "90,00 ₺"
    assert len(db.saving_goals) == 1
    assert db.saving_goals[0].created_by == "agent"


def test_build_saving_goal_progress_reads_active_scoped_goal() -> None:
    user = make_user()
    market = make_category("Market")
    goal = make_saving_goal(user_id=user.id, category_id=market.id)
    db = FakeSession(
        categories=[market],
        saving_goals=[goal],
        transactions=[
            make_transaction(
                user_id=user.id,
                category_id=market.id,
                amount="200.00",
                occurred_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
            ),
        ],
    )

    result = build_saving_goal_progress(
        db,
        user,
        category="Market",
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert result["category_name"] == "Market"
    assert result["actual_spending"] == "200.00"
    assert result["remaining_limit_formatted"] == "310,00 ₺"
    assert result["status_label"] == "on_track"


def test_build_smart_saving_plan_creates_top_category_goals() -> None:
    user = make_user()
    market = make_category("Market")
    transport = make_category("Ulaşım")
    db = FakeSession(
        categories=[market, transport],
        transactions=[
            make_transaction(
                user_id=user.id,
                category_id=market.id,
                amount="900.00",
                occurred_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
            ),
            make_transaction(
                user_id=user.id,
                category_id=transport.id,
                amount="400.00",
                occurred_at=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
            ),
        ],
        subscriptions=[make_subscription(user_id=user.id, amount="120.00")],
    )

    result = build_smart_saving_plan(
        db,
        user,
        message="Bu yaz tatile gitmek istiyorum, giderlerimi kısmam lazım.",
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert result["target_label"] == "Tatil"
    assert result["total_expense_formatted"] == "1.300,00 ₺"
    assert result["created_goal_count"] == 2
    assert result["expected_monthly_saving_formatted"] == "195,00 ₺"
    assert result["subscription_monthly_total_formatted"] == "120,00 ₺"
    assert len(db.saving_goals) == 2
