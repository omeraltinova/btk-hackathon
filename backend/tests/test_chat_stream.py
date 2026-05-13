from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.auth import create_token
from app.db import get_db
from app.main import app
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.saving_goal import SavingGoal
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.services.agent_runner import _graph_context_messages


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
        return FakeResult([])

    def add(self, item: object) -> None:
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

    def commit(self) -> None:
        return None

    def refresh(self, item: object) -> None:
        if isinstance(item, Conversation) and item.id is None:
            item.id = uuid4()
        if isinstance(item, SavingGoal) and item.id is None:
            item.id = uuid4()

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


def make_subscription(user_id: UUID, amount: str = "120.00") -> Subscription:
    return Subscription(
        id=uuid4(),
        user_id=user_id,
        name="Dijital servis",
        merchant="Servis",
        amount=Decimal(amount),
        billing_cycle="monthly",
        recurrence_interval=1,
        recurrence_unit="month",
        next_billing_date=date(2026, 6, 1),
        category_id=None,
        is_active=True,
        detected_from_transactions=False,
        usage_score=Decimal("0.50"),
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
    assert '"tool_name": "create_saving_goal"' in response.text
    assert "Market için tasarruf hedefini oluşturdum" in response.text
    assert "510,00" in response.text
    assert "altında" in response.text
    assert len(fake_session.saving_goals) == 1
    assert fake_session.saving_goals[0].created_by == "agent"


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
    assert '"tool_name": "create_smart_saving_plan"' in response.text
    assert "Tatil hedefin için" in response.text
    assert "Market" in response.text
    assert len(fake_session.saving_goals) == 2


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
