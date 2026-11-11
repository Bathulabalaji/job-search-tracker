from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserStatus
from app.models.user import User
from tests.conftest import NOW

try:  # Starlette's TestClient uses httpx2 when it is installed, else httpx.
    from httpx2 import Response
except ImportError:  # pragma: no cover
    from httpx import Response  # type: ignore[assignment]

__all__ = ["API", "PASSWORD", "Response", "login", "make_user", "move_clock", "sign_in"]

PASSWORD = "Correct-Horse-9"
API = "/api/v1"


def make_user(
    db: Session,
    email: str = "alice@example.com",
    *,
    password: str | None = PASSWORD,
    verified: bool = True,
    name: str = "Alice Walker",
    status: UserStatus = UserStatus.active,
) -> User:
    user = User(
        email=email,
        full_name=name,
        password_hash=hash_password(password) if password else None,
        status=status,
        email_verified_at=NOW if verified else None,
    )
    db.add(user)
    db.flush()
    return user


def move_clock(client: TestClient, delta: timedelta) -> None:
    """Jump the fake clock forward (sessions, tokens and rate limits all read it)."""
    client.app_state_now["value"] = NOW + delta  # type: ignore[attr-defined]


def login(
    client: TestClient, email: str = "alice@example.com", password: str = PASSWORD
) -> Response:
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def sign_in(
    client: TestClient, email: str = "alice@example.com", password: str = PASSWORD
) -> dict[str, str]:
    """Sign in and return the CSRF header to send on state-changing requests."""
    response = login(client, email, password)
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}
