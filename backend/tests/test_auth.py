from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import create_token, hash_password, verify_password, verify_token
from app.db import get_db
from app.main import app
from app.models.user import User


class FakeResult:
    def __init__(self, user: User | None) -> None:
        self._user = user

    def scalar_one_or_none(self) -> User | None:
        return self._user


class FakeSession:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.did_rollback = False

    def execute(self, statement: object) -> FakeResult:
        email = self._lookup(statement, "email")
        if isinstance(email, str):
            return FakeResult(next((user for user in self.users if user.email == email), None))

        user_id = self._lookup(statement, "id")
        if isinstance(user_id, UUID):
            return FakeResult(next((user for user in self.users if user.id == user_id), None))

        return FakeResult(None)

    def add(self, user: User) -> None:
        if user.id is None:
            user.id = uuid4()
        if user.parent_id is None:
            user.parent_id = None
        if user.is_demo is None:
            user.is_demo = False
        self.users.append(user)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        self.did_rollback = True

    def refresh(self, user: User) -> None:
        if user.id is None:
            user.id = uuid4()

    @staticmethod
    def _lookup(statement: object, column_name: str) -> object:
        for criterion in getattr(statement, "_where_criteria", ()):
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            if getattr(left, "name", None) == column_name:
                return getattr(right, "value", None)
        return None


@pytest.fixture
def fake_session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(fake_session: FakeSession) -> Iterator[TestClient]:
    def override_db() -> Iterator[FakeSession]:
        yield fake_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(
    *,
    email: str = "ayse@example.com",
    password_hash: str | None = None,
    role: str = "parent",
) -> User:
    return User(
        id=uuid4(),
        email=email,
        name="Ayşe Yılmaz",
        role=role,
        parent_id=None,
        password_hash=password_hash,
        birth_date=date(1988, 1, 1) if role != "child" else date(2014, 1, 1),
        finance_level="child" if role == "child" else "beginner",
        is_demo=False,
    )


def test_register_creates_user_and_returns_token(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "email": "AYSE@example.com",
            "password": "guvenli-sifre-123",
            "name": "Ayşe   Yılmaz",
            "role": "parent",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in_days"] == 7
    assert body["user"]["email"] == "ayse@example.com"
    assert body["user"]["name"] == "Ayşe Yılmaz"
    assert body["user"]["role"] == "parent"
    assert fake_session.users[0].password_hash != "guvenli-sifre-123"
    assert verify_token(body["access_token"])["sub"] == str(fake_session.users[0].id)


def test_register_rejects_duplicate_email(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    fake_session.users.append(make_user(email="ayse@example.com", password_hash="hash"))

    response = client.post(
        "/api/auth/register",
        json={
            "email": "ayse@example.com",
            "password": "guvenli-sifre-123",
            "name": "Ayşe Yılmaz",
            "role": "parent",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Bu e-posta adresiyle kayıtlı bir hesap var."


def test_login_returns_token_for_valid_credentials(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    user = make_user(password_hash=hash_password("guvenli-sifre-123"))
    fake_session.users.append(user)

    response = client.post(
        "/api/auth/login",
        json={"email": "ayse@example.com", "password": "guvenli-sifre-123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == str(user.id)
    assert verify_token(body["access_token"])["sub"] == str(user.id)


def test_login_rejects_wrong_password(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    fake_session.users.append(make_user(password_hash=hash_password("dogru-sifre-123")))

    response = client.post(
        "/api/auth/login",
        json={"email": "ayse@example.com", "password": "yanlis-sifre"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "E-posta veya şifre hatalı."


def test_login_rejects_child_without_password(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    fake_session.users.append(make_user(email="elif@example.com", role="child", password_hash=None))

    response = client.post(
        "/api/auth/login",
        json={"email": "elif@example.com", "password": "herhangi-bir-sifre"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "E-posta veya şifre hatalı."


def test_me_returns_current_user(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    user = make_user(password_hash=hash_password("guvenli-sifre-123"))
    fake_session.users.append(user)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {create_token(user.id)}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "ayse@example.com"


def test_update_me_changes_profile_info(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    user = make_user(password_hash=hash_password("guvenli-sifre-123"))
    fake_session.users.append(user)

    response = client.patch(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {create_token(user.id)}"},
        json={
            "email": "AYSE.YENI@example.com",
            "name": "  Ayşe   Yeni  ",
            "birth_date": "1987-01-01",
            "finance_level": "intermediate",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ayse.yeni@example.com"
    assert body["name"] == "Ayşe Yeni"
    assert body["birth_date"] == "1987-01-01"
    assert body["age"] is not None
    assert body["finance_level"] == "intermediate"


def test_update_me_rejects_duplicate_email(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    user = make_user(email="ayse@example.com", password_hash=hash_password("guvenli-sifre-123"))
    other = make_user(email="mehmet@example.com", password_hash=hash_password("guvenli-sifre-123"))
    fake_session.users.extend([user, other])

    response = client.patch(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {create_token(user.id)}"},
        json={"email": "mehmet@example.com"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Bu e-posta adresiyle kayıtlı bir hesap var."


def test_update_me_changes_password_when_current_password_matches(
    client: TestClient,
    fake_session: FakeSession,
) -> None:
    user = make_user(password_hash=hash_password("eski-sifre-123"))
    fake_session.users.append(user)

    response = client.patch(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {create_token(user.id)}"},
        json={"current_password": "eski-sifre-123", "new_password": "yeni-sifre-123"},
    )

    assert response.status_code == 200
    assert user.password_hash is not None
    assert verify_password("yeni-sifre-123", user.password_hash)


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Yetkilendirme başlığı eksik."


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer gecersiz"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Geçersiz oturum."
