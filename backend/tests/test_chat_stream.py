from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from pytest import MonkeyPatch

from app.agent.prompts import build_system_prompt
from app.auth import create_token
from app.db import get_db
from app.main import app
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.memory import AgentMemory
from app.models.message import Message
from app.models.saving_goal import SavingGoal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.chat import ChatStreamRequest
from app.services.agent_runner import _graph_context_messages, _stream_live_graph


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
        user: User,
        categories: list[Category],
        transactions: list[Transaction],
        subscriptions: list[Subscription] | None = None,
    ):
        self.users = [user]
        self.categories = categories
        self.transactions = transactions
        self.subscriptions = subscriptions or []
        self.saving_goals: list[SavingGoal] = []
        self.memories: list[AgentMemory] = []
        self.conversations: list[Conversation] = []
        self.messages: list[Message] = []

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is User:
            user_id = self._lookup(statement, "id")
            return FakeResult([user for user in self.users if user.id == user_id])
        if entity is Conversation:
            conversation_id = self._lookup(statement, "id")
            return FakeResult(
                [
                    conversation
                    for conversation in self.conversations
                    if conversation.id == conversation_id
                ],
            )
        if entity is Category:
            return FakeResult(self.categories)
        if entity is Transaction:
            return FakeResult(
                [
                    transaction
                    for transaction in self.transactions
                    if self._matches_transaction(statement, transaction)
                ],
            )
        if entity is Subscription:
            return FakeResult(self.subscriptions)
        if entity is Message:
            messages = [
                message for message in self.messages if self._matches_message(statement, message)
            ]
            limit_clause = getattr(statement, "_limit_clause", None)
            limit_value = getattr(limit_clause, "value", None)
            return FakeResult(list(reversed(messages))[:limit_value])
        if entity is SavingGoal:
            return FakeResult(
                [goal for goal in self.saving_goals if self._matches_goal(statement, goal)],
            )
        if entity is AgentMemory:
            return FakeResult(
                [memory for memory in self.memories if self._matches_memory(statement, memory)],
            )
        return FakeResult([])

    def add(self, item: object) -> None:
        if isinstance(item, Category):
            if item.id is None:
                item.id = uuid4()
            self.categories.append(item)
        if isinstance(item, Conversation):
            if item.id is None:
                item.id = uuid4()
            self.conversations.append(item)
        if isinstance(item, Message):
            if item.id is None:
                item.id = uuid4()
            self.messages.append(item)
        if isinstance(item, SavingGoal):
            if item.id is None:
                item.id = uuid4()
            self.saving_goals.append(item)
        if isinstance(item, AgentMemory):
            if item.id is None:
                item.id = uuid4()
            self.memories.append(item)

    def commit(self) -> None:
        return None

    def refresh(self, item: object) -> None:
        if isinstance(item, Category) and item.id is None:
            item.id = uuid4()
        if isinstance(item, Conversation) and item.id is None:
            item.id = uuid4()
        if isinstance(item, SavingGoal) and item.id is None:
            item.id = uuid4()
        if isinstance(item, AgentMemory) and item.id is None:
            item.id = uuid4()

    def delete(self, item: object) -> None:
        if isinstance(item, SavingGoal):
            self.saving_goals = [goal for goal in self.saving_goals if goal is not item]

    @staticmethod
    def _lookup(statement: object, column_name: str) -> object:
        for criterion in getattr(statement, "_where_criteria", ()):
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            if getattr(left, "name", None) == column_name:
                return getattr(right, "value", None)
        return None

    def _matches_transaction(self, statement: object, transaction: Transaction) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "user_id" and not self._matches_user_id(value, transaction.user_id):
                return False
            if column_name == "category_id" and transaction.category_id != value:
                return False
            if column_name == "type" and transaction.type != value:
                return False
            if column_name == "occurred_at":
                operator_name = getattr(getattr(criterion, "operator", None), "__name__", "")
                if operator_name == "ge" and transaction.occurred_at < value:
                    return False
                if operator_name == "lt" and transaction.occurred_at >= value:
                    return False
        return True

    def _matches_message(self, statement: object, message: Message) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "conversation_id" and message.conversation_id != value:
                return False
            if column_name == "role" and not self._matches_role(value, message.role):
                return False
        return True

    def _matches_goal(self, statement: object, goal: SavingGoal) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "user_id" and not self._matches_user_id(value, goal.user_id):
                return False
            if column_name == "category_id" and goal.category_id != value:
                return False
            if column_name == "status" and goal.status != value:
                return False
        return True

    def _matches_memory(self, statement: object, memory: AgentMemory) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "user_id" and not self._matches_user_id(value, memory.user_id):
                return False
            if column_name == "key" and memory.key != value:
                return False
        return True

    @staticmethod
    def _matches_user_id(value: object, user_id: UUID) -> bool:
        if isinstance(value, list | tuple | set):
            return user_id in value
        return user_id == value

    @staticmethod
    def _matches_role(value: object, role: str) -> bool:
        if isinstance(value, list | tuple | set):
            return role in value
        return role == value


def make_user() -> User:
    user = User(
        id=uuid4(),
        email="ayse@example.com",
        name="Ayşe Yılmaz",
        role="parent",
        parent_id=None,
        password_hash="hash",
        birth_date=date(1988, 1, 1),
        finance_level="beginner",
        is_demo=False,
    )
    user.children = []
    return user


def test_system_prompt_rejects_investment_advice() -> None:
    prompt = build_system_prompt(role="parent", level="beginner")

    assert "Asla yatırım tavsiyesi verme" in prompt
    assert "Yatırım tavsiyesi veremem" in prompt


def make_subscription(user_id: UUID, amount: str = "120.00") -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user_id,
        name="Dijital servis",
        merchant="Servis",
        amount=Decimal(amount),
        type="expense",
        billing_cycle="monthly",
        recurrence_interval=1,
        recurrence_unit="month",
        next_billing_date=date(2026, 6, 1),
        category_id=None,
        is_active=True,
        detected_from_transactions=False,
        usage_score=Decimal("0.50"),
    )


def make_goal(
    *,
    user_id: UUID,
    goal_type: str,
    category_id: UUID | None = None,
) -> SavingGoal:
    if goal_type == "accumulation":
        return SavingGoal(
            id=uuid4(),
            user_id=user_id,
            goal_type="accumulation",
            category_id=None,
            title="Tatil birikimi",
            baseline_amount=Decimal("6000.00"),
            target_spending_amount=Decimal("24000.00"),
            target_saving_amount=Decimal("18000.00"),
            target_amount=Decimal("24000.00"),
            current_amount=Decimal("6000.00"),
            monthly_contribution=Decimal("1500.00"),
            start_date=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
            end_date=datetime(2027, 5, 1, 0, 0, tzinfo=UTC),
            status="active",
            strategy={"tactics": ["Aylık hedef katkıyı ayrı takip et."]},
            created_by="agent",
        )
    return SavingGoal(
        id=uuid4(),
        user_id=user_id,
        goal_type="expense_reduction",
        category_id=category_id,
        title="Market harcamamı azalt",
        baseline_amount=Decimal("600.00"),
        target_spending_amount=Decimal("510.00"),
        target_saving_amount=Decimal("90.00"),
        target_amount=None,
        current_amount=Decimal("0"),
        monthly_contribution=None,
        start_date=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        end_date=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
        status="active",
        strategy={"tactics": ["Haftalık üst limitini takip et."]},
        created_by="agent",
    )


def test_graph_context_includes_recent_user_and_assistant_messages() -> None:
    user = make_user()
    conversation = Conversation(id=uuid4(), user_id=user.id)
    fake_session = FakeSession(user, [], [])
    fake_session.conversations.append(conversation)
    old_user = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        role="user",
        content="Geçen mesajda hedefim kumbara demiştim.",
    )
    old_tool = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        role="tool",
        content="Araç sonucu alındı.",
        tool_name="get_user_memory",
    )
    old_assistant = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content="Kumbara hedefini not aldım.",
    )
    current_user = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        role="user",
        content="Bunu hatırlıyor musun?",
    )
    fake_session.messages.extend([old_user, old_tool, old_assistant, current_user])

    context = _graph_context_messages(
        fake_session,
        conversation,
        current_user_message=current_user,
        current_user_content="Bunu hatırlıyor musun?\n\nFiş OCR sonucu: yok",
    )

    assert [message.type for message in context] == ["human", "ai", "human"]
    assert [str(message.content) for message in context] == [
        "Geçen mesajda hedefim kumbara demiştim.",
        "Kumbara hedefini not aldım.",
        "Bunu hatırlıyor musun?\n\nFiş OCR sonucu: yok",
    ]


def test_live_graph_mutating_tool_call_is_intercepted_for_approval(
    monkeypatch: MonkeyPatch,
) -> None:
    user = make_user()
    conversation = Conversation(id=uuid4(), user_id=user.id)
    current_user_message = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        role="user",
        content="Eğlence harcamam için hedef oluştur.",
    )
    fake_session = FakeSession(user, [], [])
    fake_session.conversations.append(conversation)
    fake_session.messages.append(current_user_message)

    class FakeGraph:
        def stream(self, _state: object, *, stream_mode: str) -> Iterator[dict[str, object]]:
            assert stream_mode == "updates"
            yield {
                "agent": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "id": "call-1",
                                    "name": "create_saving_goal",
                                    "args": {
                                        "category": "Eğlence",
                                        "target_reduction_percent": 15,
                                    },
                                },
                            ],
                        ),
                    ],
                },
            }

    monkeypatch.setattr(
        "app.services.agent_runner.build_agent_graph_from_settings",
        lambda _settings=None: FakeGraph(),
    )

    events = list(
        _stream_live_graph(
            fake_session,
            user,
            ChatStreamRequest(
                message="Eğlence harcamam için hedef oluştur.",
                conversation_id=conversation.id,
            ),
            conversation,
            current_user_message=current_user_message,
            settings=None,
        ),
    )

    assert any(event["type"] == "approval_required" for event in events)
    assert not any(event["type"] == "tool_call" for event in events)
    approval_event = next(event for event in events if event["type"] == "approval_required")
    assert approval_event["tool_name"] == "create_saving_goal"
    assert "Eğlence kategorisi" in str(approval_event["summary"])
    assert fake_session.messages[-2].role == "tool"
    assert fake_session.messages[-2].tool_calls is not None
    assert fake_session.messages[-2].tool_calls["status"] == "pending"


def test_chat_stream_returns_sse_tool_trace_from_scoped_data() -> None:
    user = make_user()
    category = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=Decimal("600.00"),
    )
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("125.00"),
        type="expense",
        category_id=category.id,
        description="Alışveriş",
        merchant="Market",
        occurred_at=datetime.now(UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )
    fake_session = FakeSession(user, [category], [transaction])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Bu ay markete ne kadar harcadım?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: tool_call" in response.text
    assert '"tool_name": "get_spending"' in response.text
    assert "125,00 ₺" in response.text
    assert "Market zarfında" in response.text
    assert "475,00 ₺ kaldı" in response.text
    assert [message.role for message in fake_session.messages] == ["user", "tool", "assistant"]


def test_chat_stream_routes_harclik_zarf_to_spending_not_concept() -> None:
    user = make_user()
    category = Category(
        id=uuid4(),
        user_id=None,
        name="Harçlık",
        icon=None,
        parent_id=None,
        budget_monthly=Decimal("300.00"),
    )
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("120.00"),
        type="expense",
        category_id=category.id,
        description="Harçlık",
        merchant="Harçlık",
        occurred_at=datetime.now(UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )
    fake_session = FakeSession(user, [category], [transaction])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Harçlık zarfında ne kadar kaldı?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "get_spending"' in response.text
    assert '"tool_name": "explain_concept"' not in response.text
    assert "Harçlık zarfında" in response.text
    assert "180,00 ₺ kaldı" in response.text


def test_chat_stream_can_create_category_saving_goal() -> None:
    user = make_user()
    category = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("600.00"),
        type="expense",
        category_id=category.id,
        description="Market alışverişi",
        merchant="Market",
        occurred_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )
    fake_session = FakeSession(user, [category], [transaction])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Market harcamamı azaltmak istiyorum."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "event: approval_required" in response.text
    assert '"tool_name": "create_saving_goal"' in response.text
    assert "Market kategorisi için %15 azaltma hedefi oluşturulacak" in response.text
    assert len(fake_session.saving_goals) == 0


def test_chat_stream_runs_approved_saving_goal_creation() -> None:
    user = make_user()
    category = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("600.00"),
        type="expense",
        category_id=category.id,
        description="Market alışverişi",
        merchant="Market",
        occurred_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )
    conversation = Conversation(id=uuid4(), user_id=user.id)
    approval_id = "approval-test"
    fake_session = FakeSession(user, [category], [transaction])
    fake_session.conversations.append(conversation)
    fake_session.messages.append(
        Message(
            id=uuid4(),
            conversation_id=conversation.id,
            role="tool",
            content="Kullanıcı onayı bekleniyor.",
            tool_name="create_saving_goal",
            tool_calls={
                "approval_id": approval_id,
                "tool_name": "create_saving_goal",
                "input": {"category": "Market", "target_reduction_percent": 15},
                "action_label": "Tasarruf hedefi oluştur",
                "summary": "Market kategorisi için %15 azaltma hedefi oluşturulacak.",
                "details": [],
                "status": "pending",
            },
        ),
    )

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={
                "message": "Bu işlemi onaylıyorum.",
                "conversation_id": str(conversation.id),
                "approval_id": approval_id,
                "approval_decision": "approved",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "create_saving_goal"' in response.text
    assert "Market için tasarruf hedefini oluşturdum" in response.text
    assert "510,00" in response.text
    assert len(fake_session.saving_goals) == 1
    assert fake_session.saving_goals[0].created_by == "agent"
    assert fake_session.messages[0].tool_calls is not None
    assert fake_session.messages[0].tool_calls["status"] == "approved"


def test_chat_stream_runs_approved_saving_goal_with_localized_percent() -> None:
    user = make_user()
    category = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("600.00"),
        type="expense",
        category_id=category.id,
        description="Market alışverişi",
        merchant="Market",
        occurred_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )
    conversation = Conversation(id=uuid4(), user_id=user.id)
    approval_id = "approval-percent"
    fake_session = FakeSession(user, [category], [transaction])
    fake_session.conversations.append(conversation)
    fake_session.messages.append(
        Message(
            id=uuid4(),
            conversation_id=conversation.id,
            role="tool",
            content="Kullanıcı onayı bekleniyor.",
            tool_name="create_saving_goal",
            tool_calls={
                "approval_id": approval_id,
                "tool_name": "create_saving_goal",
                "input": {"category": "Market", "target_reduction_percent": "%15"},
                "action_label": "Tasarruf hedefi oluştur",
                "summary": "Market kategorisi için %15 azaltma hedefi oluşturulacak.",
                "details": [],
                "status": "pending",
            },
        ),
    )

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={
                "message": "Bu işlemi onaylıyorum.",
                "conversation_id": str(conversation.id),
                "approval_id": approval_id,
                "approval_decision": "approved",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Onayladığın işlemi tamamlayamadım" not in response.text
    assert len(fake_session.saving_goals) == 1
    assert fake_session.saving_goals[0].target_spending_amount == Decimal("510.00")
    assert fake_session.messages[0].tool_calls is not None
    assert fake_session.messages[0].tool_calls["status"] == "approved"


def test_chat_stream_rejects_pending_approval_without_mutation() -> None:
    user = make_user()
    conversation = Conversation(id=uuid4(), user_id=user.id)
    approval_id = "approval-reject"
    fake_session = FakeSession(user, [], [])
    fake_session.conversations.append(conversation)
    fake_session.messages.append(
        Message(
            id=uuid4(),
            conversation_id=conversation.id,
            role="tool",
            content="Kullanıcı onayı bekleniyor.",
            tool_name="create_accumulation_goal",
            tool_calls={
                "approval_id": approval_id,
                "tool_name": "create_accumulation_goal",
                "input": {
                    "title": "Tatil birikimi",
                    "target_amount": "24000.00",
                    "target_months": 12,
                },
                "action_label": "Birikim hedefi oluştur",
                "summary": "Tatil birikimi için 24.000,00 ₺ hedef açılacak.",
                "details": [],
                "status": "pending",
            },
        ),
    )

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={
                "message": "Vazgeçtim.",
                "conversation_id": str(conversation.id),
                "approval_id": approval_id,
                "approval_decision": "rejected",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "herhangi bir değişiklik yapmadım" in response.text
    assert '"tool_name": "create_accumulation_goal"' not in response.text
    assert len(fake_session.saving_goals) == 0
    assert fake_session.messages[0].tool_calls is not None
    assert fake_session.messages[0].tool_calls["status"] == "rejected"


def test_chat_stream_requests_approval_before_envelope_budget_creation() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Evcil hayvan için zarf oluştur, limiti 850 TL olsun."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "event: approval_required" in response.text
    assert '"tool_name": "create_envelope_budget"' in response.text
    assert "Evcil Hayvan zarfı için aylık limit 850,00 ₺ yapılacak" in response.text


def test_chat_stream_runs_approved_envelope_with_localized_live_amount() -> None:
    user = make_user()
    conversation = Conversation(id=uuid4(), user_id=user.id)
    approval_id = "approval-envelope-localized"
    fake_session = FakeSession(user, [], [])
    fake_session.conversations.append(conversation)
    fake_session.messages.append(
        Message(
            id=uuid4(),
            conversation_id=conversation.id,
            role="tool",
            content="Kullanıcı onayı bekleniyor.",
            tool_name="create_envelope_budget",
            tool_calls={
                "approval_id": approval_id,
                "tool_name": "create_envelope_budget",
                "input": {"name": "Eğlence", "budget_monthly": "1.250 ₺"},
                "action_label": "Zarf ekle",
                "summary": "Eğlence zarfı için aylık limit 1.250,00 ₺ yapılacak.",
                "details": [],
                "status": "pending",
            },
        ),
    )

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={
                "message": "Bu işlemi onaylıyorum.",
                "conversation_id": str(conversation.id),
                "approval_id": approval_id,
                "approval_decision": "approved",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "create_envelope_budget"' in response.text
    assert "Onayladığın işlemi tamamlayamadım" not in response.text
    assert "Eğlence zarfını 1.250,00 ₺ aylık limit ile" in response.text
    assert "kaydettim" in response.text
    custom_category = next(
        category for category in fake_session.categories if category.name == "Eğlence"
    )
    assert custom_category.user_id == user.id
    assert custom_category.budget_monthly == Decimal("1250.00")
    assert fake_session.messages[0].tool_calls is not None
    assert fake_session.messages[0].tool_calls["status"] == "approved"


def test_chat_stream_runs_approved_accumulation_with_localized_amounts_and_months() -> None:
    user = make_user()
    conversation = Conversation(id=uuid4(), user_id=user.id)
    approval_id = "approval-accumulation-localized"
    fake_session = FakeSession(user, [], [])
    fake_session.conversations.append(conversation)
    fake_session.messages.append(
        Message(
            id=uuid4(),
            conversation_id=conversation.id,
            role="tool",
            content="Kullanıcı onayı bekleniyor.",
            tool_name="create_accumulation_goal",
            tool_calls={
                "approval_id": approval_id,
                "tool_name": "create_accumulation_goal",
                "input": {
                    "title": "Tatil birikimi",
                    "target_amount": "24.000,00 ₺",
                    "current_amount": "6.000,00 ₺",
                    "monthly_contribution": "1.500,00 ₺",
                    "target_months": "12 ay",
                },
                "action_label": "Birikim hedefi oluştur",
                "summary": "Tatil birikimi için 24.000,00 ₺ hedef açılacak.",
                "details": [],
                "status": "pending",
            },
        ),
    )

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={
                "message": "Bu işlemi onaylıyorum.",
                "conversation_id": str(conversation.id),
                "approval_id": approval_id,
                "approval_decision": "approved",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Onayladığın işlemi tamamlayamadım" not in response.text
    assert len(fake_session.saving_goals) == 1
    goal = fake_session.saving_goals[0]
    assert goal.target_amount == Decimal("24000.00")
    assert goal.current_amount == Decimal("6000.00")
    assert goal.monthly_contribution == Decimal("1500.00")
    assert fake_session.messages[0].tool_calls is not None
    assert fake_session.messages[0].tool_calls["status"] == "approved"


def test_chat_stream_can_create_accumulation_goal() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Tatil için 24000 TL birikim hedefi oluştur."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "event: approval_required" in response.text
    assert '"tool_name": "create_accumulation_goal"' in response.text
    assert "Tatil birikimi için 24.000,00 ₺ hedef açılacak" in response.text
    assert len(fake_session.saving_goals) == 0


def test_chat_stream_can_show_goals_with_chart_payload() -> None:
    user = make_user()
    market = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("540.00"),
        type="expense",
        category_id=market.id,
        description="Market alışverişi",
        merchant="Market",
        occurred_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )
    fake_session = FakeSession(user, [market], [transaction])
    fake_session.saving_goals.extend(
        [
            make_goal(user_id=user.id, goal_type="accumulation"),
            make_goal(user_id=user.id, goal_type="expense_reduction", category_id=market.id),
        ],
    )

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Mevcut birikim ve tasarruf hedeflerimi grafikle göster."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "get_saving_goals"' in response.text
    assert '"tool_name": "visualize_saving_goals"' in response.text
    assert '"chart"' in response.text
    assert "Aktif 2 hedefin var" in response.text
    assert "/dashboard/goals" in response.text


def test_chat_stream_can_create_smart_saving_plan() -> None:
    user = make_user()
    market = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    transport = Category(
        id=uuid4(),
        user_id=None,
        name="Ulaşım",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    transactions = [
        Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("900.00"),
            type="expense",
            category_id=market.id,
            description="Market alışverişi",
            merchant="Market",
            occurred_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
            source="manual",
            receipt_image_url=None,
            raw_ocr_data=None,
        ),
        Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("400.00"),
            type="expense",
            category_id=transport.id,
            description="Ulaşım",
            merchant="Metro",
            occurred_at=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
            source="manual",
            receipt_image_url=None,
            raw_ocr_data=None,
        ),
    ]
    fake_session = FakeSession(
        user,
        [market, transport],
        transactions,
        subscriptions=[make_subscription(user.id)],
    )

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Bu yaz tatile gitmek istiyorum, giderlerimi kısmam lazım."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "event: approval_required" in response.text
    assert '"tool_name": "create_smart_saving_plan"' in response.text
    assert "Son 30 gün verisine göre hedef planı oluşturulacak" in response.text
    assert len(fake_session.saving_goals) == 0


def test_chat_stream_smart_plan_mentions_accumulation_without_spending_data() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Tatil için 24000 TL biriktirmek istiyorum, nereden kısmalıyım?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "event: approval_required" in response.text
    assert '"tool_name": "create_smart_saving_plan"' in response.text
    assert "Son 30 gün verisine göre hedef planı oluşturulacak" in response.text
    assert len(fake_session.saving_goals) == 0


def test_chat_stream_returns_inline_chart_payload() -> None:
    user = make_user()
    category = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("125.00"),
        type="expense",
        category_id=category.id,
        description="Alışveriş",
        merchant="Market",
        occurred_at=datetime.now(UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )
    fake_session = FakeSession(user, [category], [transaction])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Harcamalarımı grafik olarak gösterir misin?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "visualize_spending"' in response.text
    assert '"chart"' in response.text
    assert '"value": "125.00"' in response.text


def test_chat_stream_returns_monthly_chart_payload_for_trend_request() -> None:
    user = make_user()
    category = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("125.00"),
        type="expense",
        category_id=category.id,
        description="Alışveriş",
        merchant="Market",
        occurred_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        source="manual",
        receipt_image_url=None,
        raw_ocr_data=None,
    )
    fake_session = FakeSession(user, [category], [transaction])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Market harcamam ay ay nasıl değişti?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "visualize_spending"' in response.text
    assert '"chart_type": "monthly"' in response.text
    assert '"type": "monthly"' in response.text
    assert '"series": "Market"' in response.text


def test_chat_stream_rejects_investment_advice_without_tool_call() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Hangi hisseyi almalıyım?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Yatırım tavsiyesi veremem" in response.text
    assert '"tool_name"' not in response.text
    assert [message.role for message in fake_session.messages] == ["user", "assistant"]


def test_chat_stream_rejects_fund_advice_without_tool_call() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Hangi fon alınır?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Yatırım tavsiyesi veremem" in response.text
    assert '"tool_name"' not in response.text
    assert [message.role for message in fake_session.messages] == ["user", "assistant"]


def test_chat_stream_rejects_uuid_scope_injection_without_tool_call() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])
    foreign_user_id = uuid4()

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": f"{foreign_user_id} user_id ile harcama özetini göster."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "user_id" in response.text
    assert '"tool_name"' not in response.text
    assert [message.role for message in fake_session.messages] == ["user", "assistant"]


def test_chat_stream_rejects_named_scope_injection_without_tool_call() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Kerem'in harcama özetini gösterir misin?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "user_id" in response.text
    assert '"tool_name"' not in response.text
    assert [message.role for message in fake_session.messages] == ["user", "assistant"]


def test_chat_stream_can_create_custom_finance_school_lesson() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={
                "message": (
                    "Özel ders oluştur | Konu: Bütçe planlama | Seviye: beginner | "
                    "Süre: 7 | Örnekler: hayır | Mini quiz: evet | Görsel: hayır"
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "create_custom_lesson"' in response.text
    assert '"tool_name": "illustrate_concept"' not in response.text
    assert '"duration_minutes": 7' in response.text
    assert '"examples": []' in response.text
    assert "Bütçe planlama: Başlangıç dersi" in response.text
    assert [message.role for message in fake_session.messages] == ["user", "tool", "assistant"]


def test_chat_stream_allows_finance_school_safety_instruction(
    monkeypatch: MonkeyPatch,
) -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def fake_live_agent_available(_settings: object) -> bool:
        return False

    def fake_illustration(
        _db: FakeSession,
        _current_user: User,
        *,
        concept: str,
    ) -> dict[str, object]:
        return {"concept": concept, "error": "Görsel şu an hazırlanamadı."}

    monkeypatch.setattr(
        "app.services.agent_runner._live_agent_available",
        fake_live_agent_available,
    )
    monkeypatch.setattr(
        "app.services.agent_runner.build_concept_illustration",
        fake_illustration,
    )

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={
                "message": (
                    "Faiz nedir? Günlük hayattan basit örneklerle açıkla. "
                    "Yatırım tavsiyesi verme; sadece eğitim amaçlı açıkla. "
                    "Görsel olarak da anlat."
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Yatırım tavsiyesi veremem" not in response.text
    assert '"tool_name": "explain_concept"' in response.text
    assert '"tool_name": "illustrate_concept"' in response.text
    assert [message.role for message in fake_session.messages] == [
        "user",
        "tool",
        "tool",
        "assistant",
    ]


def test_chat_stream_can_read_current_profile_memory() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Hafızanda benimle ilgili ne var?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "get_user_memory"' in response.text
    assert "Hafızamda bu profil için" in response.text
    assert "kayıtlı bir bilgi" in response.text
    assert "bulamadım" in response.text


def test_chat_stream_can_write_explicit_current_profile_memory() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Bunu hatırla: kahveyi şekersiz içerim"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "remember_user_memory"' in response.text
    assert "hafızasına kaydettim" in response.text
    assert len(fake_session.memories) == 1
    assert fake_session.memories[0].user_id == user.id
    assert fake_session.memories[0].value == {
        "text": "kahveyi şekersiz içerim",
        "source": "chat",
    }


def test_chat_stream_memory_write_bypasses_live_agent(monkeypatch: MonkeyPatch) -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    monkeypatch.setattr("app.services.agent_runner._live_agent_available", lambda settings: True)

    def fail_live_agent(*args: object, **kwargs: object) -> Iterator[dict[str, object]]:
        raise AssertionError("explicit memory writes must not route through the live agent")
        yield {}

    monkeypatch.setattr("app.services.agent_runner._stream_live_graph", fail_live_agent)

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Bunu hatırla: markette nakit kullanmayı severim"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "remember_user_memory"' in response.text
    assert len(fake_session.memories) == 1


def test_chat_stream_blocks_sensitive_memory_write() -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Bunu hatırla: IBAN TR120006200119000006672315"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "remember_user_memory"' in response.text
    assert "hassas görünüyor" in response.text
    assert fake_session.memories == []
    tool_message = next(message for message in fake_session.messages if message.role == "tool")
    assert tool_message.tool_calls is not None
    assert tool_message.tool_calls["input"] == {"text": "[redacted]"}
    assert "TR120006200119000006672315" not in str(tool_message.tool_calls)


def test_chat_stream_emits_image_event_for_concept_illustration(
    monkeypatch: MonkeyPatch,
) -> None:
    user = make_user()
    fake_session = FakeSession(user, [], [])

    def fake_illustration(
        db: FakeSession,
        current_user: User,
        *,
        concept: str,
    ) -> dict[str, object]:
        assert db is fake_session
        assert current_user.id == user.id
        return {
            "concept": concept,
            "image_url": "http://localhost:9000/illustrations/demo/faiz.png",
            "alt_text": "Faiz kavramını anlatan görsel",
        }

    monkeypatch.setattr(
        "app.services.agent_runner.build_concept_illustration",
        fake_illustration,
    )

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={"message": "Faiz nedir, görsel olarak çizer misin?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "illustrate_concept"' in response.text
    assert "event: image" in response.text
    assert "http://localhost:9000/illustrations/demo/faiz.png" in response.text


def test_chat_stream_can_analyze_receipt_attachment_without_persisting_raw_text() -> None:
    user = make_user()
    market = Category(
        id=uuid4(),
        user_id=None,
        name="Market",
        icon=None,
        parent_id=None,
        budget_monthly=None,
    )
    receipt_text = """MIGROS TICARET A.S.
TARIH: 12.05.2026 14:32
EKMEK            15,00
SUT              42,50
MEYVE            90,00
TEMIZLIK         100,00
GENEL TOPLAM     247,50 TL
"""
    fake_session = FakeSession(user, [market], [])

    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            headers={"Authorization": f"Bearer {create_token(user.id)}"},
            json={
                "message": "Bu fişi analiz eder misin?",
                "receipt_image_base64": base64.b64encode(receipt_text.encode()).decode("ascii"),
                "receipt_filename": "migros_demo.txt",
                "receipt_content_type": "text/plain",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_name": "analyze_receipt"' in response.text
    assert "MIGROS TICARET A.S." in response.text
    assert "247,50" in response.text
    assert "₺" in response.text
    assert "raw_text" not in response.text
    assert "receipt_image_base64" not in response.text
    assert [message.role for message in fake_session.messages] == ["user", "tool", "assistant"]
