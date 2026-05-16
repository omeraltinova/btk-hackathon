from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.agent.tools import (
    build_accumulation_goal_creation,
    build_concept_illustration,
    build_custom_lesson,
    build_envelope_budget_creation,
    build_envelope_budget_delete,
    build_envelope_budget_overview,
    build_envelope_budget_update,
    build_saving_goal_creation,
    build_saving_goal_delete,
    build_saving_goal_progress,
    build_saving_goal_update,
    build_saving_goals_chart,
    build_saving_goals_overview,
    build_smart_saving_plan,
    build_spending_chart,
    build_spending_summary,
    build_subscriptions_summary,
    build_user_memory,
    infer_category_from_text,
    parse_bool_text,
    parse_goal_status_text,
    parse_int_text,
    parse_money_text,
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
            return FakeResult(
                [item for item in self.categories if self._matches_statement(statement, item)],
            )
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
        if isinstance(item, Category):
            if item.id is None:
                item.id = uuid4()
            self.categories.append(item)
        if isinstance(item, SavingGoal):
            if item.id is None:
                item.id = uuid4()
            self.saving_goals.append(item)

    def commit(self) -> None:
        return None

    def refresh(self, item: object) -> None:
        if isinstance(item, Category) and item.id is None:
            item.id = uuid4()
        if isinstance(item, SavingGoal) and item.id is None:
            item.id = uuid4()

    def delete(self, item: object) -> None:
        if isinstance(item, SavingGoal):
            self.saving_goals = [goal for goal in self.saving_goals if goal is not item]

    def _matches_statement(self, statement: object, row: object) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "id" and getattr(row, "id", None) != value:
                return False
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


def make_user_category(user_id: UUID, name: str, *, budget: str | None = None) -> Category:
    category = make_category(name, budget=budget)
    category.user_id = user_id
    return category


def make_transaction(
    *,
    user_id: UUID,
    category_id: UUID | None,
    amount: str,
    tx_type: str = "expense",
    merchant: str | None = "Market",
    occurred_at: datetime | None = None,
    source: str = "manual",
    raw_ocr_data: dict[str, Any] | None = None,
) -> Transaction:
    return Transaction(
        id=uuid4(),
        user_id=user_id,
        amount=Decimal(amount),
        type=tx_type,
        category_id=category_id,
        description=None,
        merchant=merchant,
        occurred_at=occurred_at or datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        source=source,
        receipt_image_url=None,
        raw_ocr_data=raw_ocr_data,
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
        goal_type="expense_reduction",
        category_id=category_id,
        title="Market harcamamı azalt",
        baseline_amount=Decimal(baseline),
        target_spending_amount=Decimal(target),
        target_saving_amount=Decimal(saving),
        target_amount=None,
        current_amount=Decimal("0"),
        monthly_contribution=None,
        start_date=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        end_date=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
        status="active",
        strategy={"tactics": ["Haftalık üst limitini takip et."]},
        created_by="agent",
    )


def make_accumulation_goal(
    *,
    user_id: UUID,
    target: str = "24000.00",
    current: str = "6000.00",
) -> SavingGoal:
    return SavingGoal(
        id=uuid4(),
        user_id=user_id,
        goal_type="accumulation",
        category_id=None,
        title="Tatil birikimi",
        baseline_amount=Decimal(current),
        target_spending_amount=Decimal(target),
        target_saving_amount=Decimal(target) - Decimal(current),
        target_amount=Decimal(target),
        current_amount=Decimal(current),
        monthly_contribution=Decimal("1500.00"),
        start_date=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        end_date=datetime(2027, 5, 1, 0, 0, tzinfo=UTC),
        status="active",
        strategy={"tactics": ["Aylık hedef katkıyı ayrı takip et."]},
        created_by="agent",
    )


def make_subscription(
    *,
    user_id: UUID,
    amount: str,
    name: str = "Dijital servis",
    merchant: str | None = "Servis",
    cycle: str = "monthly",
    is_active: bool = True,
) -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user_id,
        name=name,
        merchant=merchant,
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


def test_agent_input_parsers_accept_localized_model_values() -> None:
    assert parse_money_text("1.250,50 ₺") == Decimal("1250.50")
    assert parse_money_text("700,00 TL") == Decimal("700.00")
    assert parse_int_text("%15 azalt", default=10, min_value=1, max_value=50) == 15
    assert parse_int_text("12 ay", default=6, min_value=1, max_value=120) == 12
    assert parse_bool_text("tüm kayıtlar", default=True) is False
    assert parse_bool_text("evet", default=False) is True
    assert parse_goal_status_text("duraklatıldı") == "paused"
    assert parse_goal_status_text("aktif yap") == "active"


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


def test_build_monthly_spending_chart_matches_multiple_categories_from_query() -> None:
    user = make_user()
    market = make_category("Market")
    food = make_category("Yemek")
    bills = make_category("Fatura")
    db = FakeSession(
        categories=[market, food, bills],
        transactions=[
            make_transaction(
                user_id=user.id,
                category_id=market.id,
                amount="100.00",
                occurred_at=datetime(2026, 3, 5, 10, 0, tzinfo=UTC),
            ),
            make_transaction(
                user_id=user.id,
                category_id=food.id,
                amount="45.50",
                merchant="Lokanta",
                occurred_at=datetime(2026, 4, 5, 10, 0, tzinfo=UTC),
            ),
            make_transaction(
                user_id=user.id,
                category_id=bills.id,
                amount="999.00",
                merchant="Fatura",
                occurred_at=datetime(2026, 4, 6, 10, 0, tzinfo=UTC),
            ),
        ],
    )

    result = build_spending_chart(
        db,
        user,
        chart_type="monthly",
        query="Market ve yemek harcamam ay ay nasıl değişti?",
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )
    chart = result["chart"]

    assert result["target_type"] == "category"
    assert result["transaction_count"] == 2
    assert result["total_amount_formatted"] == "145,50 ₺"
    assert isinstance(chart, dict)
    assert chart["type"] == "monthly"
    data = chart["data"]
    assert isinstance(data, list)
    assert {point["series"] for point in data} == {"Market", "Yemek"}
    assert (
        next(
            point for point in data if point["label"] == "03.2026" and point["series"] == "Market"
        )["value"]
        == "100.00"
    )
    assert (
        next(point for point in data if point["label"] == "04.2026" and point["series"] == "Yemek")[
            "value"
        ]
        == "45.50"
    )


def test_build_monthly_spending_chart_matches_subscription_vendor_from_query() -> None:
    user = make_user()
    subscription = make_subscription(
        user_id=user.id,
        amount="149.99",
        name="Netflix",
        merchant="Netflix",
    )
    db = FakeSession(
        subscriptions=[subscription],
        transactions=[
            make_transaction(
                user_id=user.id,
                category_id=None,
                amount="149.99",
                merchant="Netflix",
                occurred_at=datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
                source="recurring",
                raw_ocr_data={
                    "subscription_id": str(subscription.id),
                    "billing_date": "2026-03-10",
                },
            ),
            make_transaction(
                user_id=user.id,
                category_id=None,
                amount="169.99",
                merchant="Netflix",
                occurred_at=datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
                source="recurring",
                raw_ocr_data={
                    "subscription_id": str(subscription.id),
                    "billing_date": "2026-04-10",
                },
            ),
        ],
    )

    result = build_spending_chart(
        db,
        user,
        chart_type="monthly",
        query="Netflix aboneliğim ay ay nasıl değişti?",
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )
    chart = result["chart"]

    assert result["target_type"] == "subscription"
    assert result["transaction_count"] == 2
    assert result["total_amount_formatted"] == "319,98 ₺"
    assert isinstance(chart, dict)
    data = chart["data"]
    assert isinstance(data, list)
    assert {point["series"] for point in data} == {"Netflix"}
    assert (
        next(
            point for point in data if point["label"] == "03.2026" and point["series"] == "Netflix"
        )["value"]
        == "149.99"
    )
    assert (
        next(
            point for point in data if point["label"] == "04.2026" and point["series"] == "Netflix"
        )["value"]
        == "169.99"
    )


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


def test_build_custom_lesson_returns_transient_structured_plan() -> None:
    user = make_user()
    user.finance_level = "child"

    result = build_custom_lesson(
        user,
        topic="Harçlık planlama",
        level="çocuk",
        duration_minutes=20,
        include_examples=False,
        include_quiz=True,
        visual=True,
    )

    assert result["title"] == "Harçlık planlama: Çocuk dersi"
    assert result["level"] == "child"
    assert result["duration_minutes"] == 12
    assert result["examples"] == []
    assert result["mini_quiz"]
    assert result["visual"] is True
    assert result["illustration_prompt"] == "Harçlık planlama"
    assert "kalıcı" not in result


def test_build_custom_lesson_rejects_product_advice_topics() -> None:
    user = make_user()

    result = build_custom_lesson(
        user,
        topic="Hangi fon alınır?",
        level="beginner",
    )

    assert result["topic"] == "Hangi fon alınır?"
    assert result["error"] == (
        "Özel ders oluşturabilirim ama belirli ürün, al-sat veya getiri tavsiyesi veremem."
    )


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


def test_agent_envelope_tools_list_update_and_disable_user_shadow_budget() -> None:
    user = make_user()
    system_market = make_category("Market", budget="600.00")
    db = FakeSession(categories=[system_market])

    overview = build_envelope_budget_overview(
        db,
        user,
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )
    update_result = build_envelope_budget_update(
        db,
        user,
        slug="market",
        budget_monthly=Decimal("900.00"),
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )
    delete_result = build_envelope_budget_delete(
        db,
        user,
        slug="market",
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert overview["count"] == 6
    assert update_result["updated"] is True
    assert update_result["budget_monthly_formatted"] == "900,00 ₺"
    user_shadow = next(category for category in db.categories if category.user_id == user.id)
    assert user_shadow.name == "Market"
    assert user_shadow.budget_monthly == Decimal("0.00")
    assert system_market.budget_monthly == Decimal("600.00")
    assert delete_result["deleted"] is True
    assert delete_result["disabled"] is True


def test_envelope_budget_summary_includes_custom_user_categories() -> None:
    user = make_user()
    custom = make_user_category(user.id, "Evcil hayvan", budget="850.00")

    result = build_envelope_budget_summary(
        categories=[custom],
        current_category_totals={custom.id: Decimal("125.00")},
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    custom_envelope = next(envelope for envelope in result.envelopes if envelope.is_custom)
    assert custom_envelope.slug == f"custom-{custom.id}"
    assert custom_envelope.label == "Evcil hayvan zarfı"
    assert custom_envelope.budget == Decimal("850.00")
    assert custom_envelope.spent == Decimal("125.00")


def test_agent_custom_envelope_delete_uses_custom_slug() -> None:
    user = make_user()
    custom = make_user_category(user.id, "Evcil hayvan", budget="850.00")
    db = FakeSession(categories=[custom])

    result = build_envelope_budget_delete(
        db,
        user,
        slug=f"custom-{custom.id}",
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert result["deleted"] is True
    assert result["disabled"] is True
    assert result["slug"] == f"custom-{custom.id}"
    assert custom.budget_monthly == Decimal("0.00")


def test_agent_can_create_custom_envelope_by_name() -> None:
    user = make_user()
    db = FakeSession()

    result = build_envelope_budget_creation(
        db,
        user,
        name="Evcil hayvan",
        budget_monthly=Decimal("850.00"),
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    created = next(category for category in db.categories if category.user_id == user.id)
    assert result["created"] is True
    assert result["slug"] == f"custom-{created.id}"
    assert result["budget_monthly_formatted"] == "850,00 ₺"
    assert created.name == "Evcil hayvan"
    assert created.budget_monthly == Decimal("850.00")


def test_agent_create_envelope_by_builtin_name_reuses_shadow_category() -> None:
    user = make_user()
    system_market = make_category("Market", budget="600.00")
    db = FakeSession(categories=[system_market])

    result = build_envelope_budget_creation(
        db,
        user,
        name="Market",
        budget_monthly=Decimal("900.00"),
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    user_shadow = next(category for category in db.categories if category.user_id == user.id)
    assert result["created"] is True
    assert result["slug"] == "market"
    assert user_shadow.name == "Market"
    assert user_shadow.budget_monthly == Decimal("900.00")
    assert system_market.budget_monthly == Decimal("600.00")


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


def test_build_saving_goal_creation_accepts_localized_reduction_percent() -> None:
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
        target_reduction_percent="%15",
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert result["created"] is True
    assert result["target_spending_amount"] == "510.00"
    assert db.saving_goals[0].strategy["reduction_percent"] == "15.0"


def test_build_accumulation_goal_creation_tracks_target_without_float() -> None:
    user = make_user()
    db = FakeSession()

    result = build_accumulation_goal_creation(
        db,
        user,
        title="Tatil birikimi",
        target_amount=Decimal("24000.00"),
        current_amount=Decimal("6000.00"),
        target_months=12,
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert result["created"] is True
    assert result["goal_type"] == "accumulation"
    assert result["target_amount"] == "24000.00"
    assert result["current_amount_formatted"] == "6.000,00 ₺"
    assert result["remaining_amount_formatted"] == "18.000,00 ₺"
    assert result["target_saving_amount"] == "18000.00"
    assert not isinstance(result["target_amount"], float)
    assert len(db.saving_goals) == 1
    assert db.saving_goals[0].category_id is None
    assert db.saving_goals[0].baseline_amount == Decimal("6000.00")


def test_build_accumulation_goal_creation_accepts_localized_months_text() -> None:
    user = make_user()
    db = FakeSession()

    result = build_accumulation_goal_creation(
        db,
        user,
        title="Tatil birikimi",
        target_amount=Decimal("24000.00"),
        current_amount=Decimal("6000.00"),
        target_months="12 ay",
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert result["created"] is True
    assert result["end_date_formatted"] == "01.05.2027"


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


def test_build_saving_goals_overview_and_chart_are_scoped_without_float() -> None:
    user = make_user()
    other = make_user()
    market = make_category("Market")
    db = FakeSession(
        categories=[market],
        saving_goals=[
            make_accumulation_goal(user_id=user.id),
            make_saving_goal(user_id=user.id, category_id=market.id),
            make_accumulation_goal(user_id=other.id, target="50000.00", current="10000.00"),
        ],
        transactions=[
            make_transaction(
                user_id=user.id,
                category_id=market.id,
                amount="700.00",
                occurred_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
            ),
        ],
    )

    overview = build_saving_goals_overview(
        db,
        user,
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )
    chart_result = build_saving_goals_chart(
        db,
        user,
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )

    assert overview["count"] == 2
    goals = overview["goals"]
    assert isinstance(goals, list)
    assert {goal["goal_type"] for goal in goals if isinstance(goal, dict)} == {
        "accumulation",
        "expense_reduction",
    }
    chart = chart_result["chart"]
    assert isinstance(chart, dict)
    assert chart["type"] == "bar"
    data = chart["data"]
    assert isinstance(data, list)
    assert len(data) == 2
    assert all(isinstance(point["value"], str) for point in data)
    assert not any(isinstance(point["value"], float) for point in data)
    market_point = next(point for point in data if point["label"] == "Market harcamamı azalt")
    assert market_point["value"] == "0.0"
    assert market_point["value_formatted"] == "%0.0"


def test_agent_goal_tools_update_and_delete_scoped_goal() -> None:
    user = make_user()
    goal = make_accumulation_goal(user_id=user.id, current="6000.00")
    db = FakeSession(saving_goals=[goal])

    update_result = build_saving_goal_update(
        db,
        user,
        title="Tatil",
        new_title="Yaz tatili birikimi",
        contribution_amount=Decimal("500.00"),
        monthly_contribution=Decimal("1750.00"),
        now=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )
    delete_result = build_saving_goal_delete(db, user, goal_id=str(goal.id))

    assert update_result["updated"] is True
    assert update_result["title"] == "Yaz tatili birikimi"
    assert update_result["current_amount"] == "6500.00"
    assert update_result["monthly_contribution"] == "1750.00"
    assert delete_result == {
        "deleted": True,
        "goal_id": str(goal.id),
        "goal_type": "accumulation",
        "title": "Yaz tatili birikimi",
    }
    assert db.saving_goals == []


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
