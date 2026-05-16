from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.models.saving_goal import SavingGoal
from app.models.user import User
from app.routers.saving_goals import update_saving_goal_endpoint
from app.schemas.saving_goal import SavingGoalUpdate


class FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalar_one_or_none(self) -> Any | None:
        return self._items[0] if self._items else None


class FakeSession:
    def __init__(self, goals: list[SavingGoal]) -> None:
        self.goals = goals
        self.committed = False

    def execute(self, statement: object) -> FakeResult:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is not SavingGoal:
            return FakeResult([])
        return FakeResult([goal for goal in self.goals if self._matches_goal(statement, goal)])

    def commit(self) -> None:
        self.committed = True

    def refresh(self, goal: SavingGoal) -> None:
        return None

    def _matches_goal(self, statement: object, goal: SavingGoal) -> bool:
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = getattr(getattr(criterion, "left", None), "name", None)
            value = getattr(getattr(criterion, "right", None), "value", None)
            if column_name == "id" and goal.id != value:
                return False
            if column_name == "user_id" and not self._matches_user_id(value, goal.user_id):
                return False
        return True

    @staticmethod
    def _matches_user_id(value: object, user_id: UUID) -> bool:
        if isinstance(value, list | tuple | set):
            return user_id in value
        return user_id == value


def make_user() -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        name="Test Kullanıcı",
        role="individual",
        parent_id=None,
        family_id=None,
        password_hash="hash",
        birth_date=date(1991, 1, 1),
        finance_level="beginner",
        is_demo=False,
    )
    user.children = []
    return user


def make_accumulation_goal(user_id: UUID, *, current: str = "1000.00") -> SavingGoal:
    return SavingGoal(
        id=uuid4(),
        user_id=user_id,
        goal_type="accumulation",
        category_id=None,
        title="Tatil birikimi",
        baseline_amount=Decimal("1000.00"),
        target_spending_amount=Decimal("5000.00"),
        target_saving_amount=Decimal("4000.00"),
        target_amount=Decimal("5000.00"),
        current_amount=Decimal(current),
        monthly_contribution=Decimal("1000.00"),
        start_date=datetime(2026, 5, 1, tzinfo=UTC),
        end_date=datetime(2026, 9, 1, tzinfo=UTC),
        status="active",
        strategy={"tactics": ["Eski taktik"]},
        created_by="manual",
    )


def test_update_goal_adds_accumulation_contribution_and_completes_at_target() -> None:
    user = make_user()
    goal = make_accumulation_goal(user.id, current="4500.00")
    db = FakeSession([goal])

    result = update_saving_goal_endpoint(
        goal.id,
        SavingGoalUpdate(contribution_amount=Decimal("500.00")),
        db=db,
        current_user=user,
    )

    assert result.current_amount == Decimal("5000.00")
    assert result.status == "completed"
    assert goal.strategy is not None
    assert goal.strategy["remaining_amount_formatted"] == "0,00 ₺"
    assert db.committed is True


def test_update_goal_pauses_scoped_row() -> None:
    user = make_user()
    goal = make_accumulation_goal(user.id)
    db = FakeSession([goal])

    result = update_saving_goal_endpoint(
        goal.id,
        SavingGoalUpdate(status="paused"),
        db=db,
        current_user=user,
    )

    assert result.status == "paused"
    assert goal.status == "paused"
    assert db.committed is True


def test_update_goal_resumes_paused_row() -> None:
    user = make_user()
    goal = make_accumulation_goal(user.id)
    goal.status = "paused"
    db = FakeSession([goal])

    result = update_saving_goal_endpoint(
        goal.id,
        SavingGoalUpdate(status="active"),
        db=db,
        current_user=user,
    )

    assert result.status == "active"
    assert goal.status == "active"
    assert db.committed is True


def test_update_goal_rejects_contribution_over_target() -> None:
    user = make_user()
    goal = make_accumulation_goal(user.id, current="4900.00")
    db = FakeSession([goal])

    with pytest.raises(HTTPException) as exc:
        update_saving_goal_endpoint(
            goal.id,
            SavingGoalUpdate(contribution_amount=Decimal("200.00")),
            db=db,
            current_user=user,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Birikim tutarı hedef tutarı aşamaz."
    assert db.committed is False


def test_update_goal_rejects_contribution_when_paused() -> None:
    user = make_user()
    goal = make_accumulation_goal(user.id)
    goal.status = "paused"
    db = FakeSession([goal])

    with pytest.raises(HTTPException) as exc:
        update_saving_goal_endpoint(
            goal.id,
            SavingGoalUpdate(contribution_amount=Decimal("100.00")),
            db=db,
            current_user=user,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Aktif olmayan hedefe katkı eklenemez."
    assert db.committed is False


def test_update_goal_rejects_other_user_row() -> None:
    user = make_user()
    other_user = make_user()
    goal = make_accumulation_goal(other_user.id)
    db = FakeSession([goal])

    with pytest.raises(HTTPException) as exc:
        update_saving_goal_endpoint(
            goal.id,
            SavingGoalUpdate(status="paused"),
            db=db,
            current_user=user,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Hedef bulunamadı."
    assert db.committed is False
