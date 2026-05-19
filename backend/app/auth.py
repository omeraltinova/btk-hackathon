"""Authentication helpers — bcrypt password hashing + JWT issuing/verifying.

WHY: This module is pure helpers and a FastAPI dependency. No routes are wired
to it on Day 1 (per master_plan §18); Day 2 will add /api/auth/register|login|me.
Keeping helpers and the `get_current_user` dependency ready unblocks Day 2.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.user import User


# -----------------------------------------------------------------------------
# Password hashing (bcrypt; argon2id is documented as alternative in §10).
# -----------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    """Return a bcrypt hash for `plain`. Never store plain text (§10)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if `plain` matches the previously stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# -----------------------------------------------------------------------------
# JWT
# -----------------------------------------------------------------------------
class TokenPayload(TypedDict):
    """Decoded shape of our JWTs. Keep it minimal — no PII beyond user_id."""

    sub: str  # user_id (UUID as string)
    exp: int  # epoch seconds
    iat: int  # epoch seconds


def create_token(user_id: UUID | str) -> str:
    """Issue a 7-day JWT for `user_id` (İK-12)."""
    settings = get_settings()
    now = datetime.now(UTC)
    # WHY plain dict[str, Any]: PyJWT's encode signature expects an invariant
    # dict; passing a TypedDict triggers a mypy variance error. The shape is
    # documented (and re-validated on decode) by `TokenPayload`.
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.jwt_expire_days)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> TokenPayload:
    """Decode and validate `token`; raise 401 on any failure."""
    settings = get_settings()
    try:
        decoded = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum süresi doldu, tekrar giriş yapın.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz oturum.",
        ) from exc

    # Narrow to TokenPayload — required keys must be present and well typed.
    sub = decoded.get("sub")
    exp = decoded.get("exp")
    iat = decoded.get("iat")
    if not isinstance(sub, str) or not isinstance(exp, int) or not isinstance(iat, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz oturum.",
        )
    return TokenPayload(sub=sub, exp=exp, iat=iat)


# -----------------------------------------------------------------------------
# FastAPI dependency
# WHY: HTTPBearer (auto_error=False) lets us produce a Turkish error message
# instead of FastAPI's default English "Not authenticated".
# -----------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the `Authorization: Bearer <jwt>` header.

    Raises 401 if the header is missing, the token is invalid/expired,
    or the user no longer exists.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yetkilendirme başlığı eksik.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_token(credentials.credentials)
    try:
        user_uuid = UUID(payload["sub"])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz oturum.",
        ) from exc

    user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı.",
        )
    return user
