"""Native apps authenticate with a bearer token instead of a cookie."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.auth_helpers import API, PASSWORD, make_user

MOBILE = {"X-Client-Type": "mobile"}


def _mobile_login(client: TestClient) -> str:
    response = client.post(
        f"{API}/auth/login",
        json={"email": "alice@example.com", "password": PASSWORD},
        headers=MOBILE,
    )
    assert response.status_code == 200, response.text
    token = response.json()["session_token"]
    assert isinstance(token, str) and len(token) > 20
    return token


def test_mobile_login_returns_a_token_and_sets_no_cookie(
    auth_client: TestClient, db: Session
) -> None:
    make_user(db)
    _mobile_login(auth_client)
    assert "session" not in auth_client.cookies


def test_browsers_never_receive_the_raw_token(auth_client: TestClient, db: Session) -> None:
    make_user(db)
    response = auth_client.post(
        f"{API}/auth/login", json={"email": "alice@example.com", "password": PASSWORD}
    )
    assert response.json()["session_token"] is None
    assert "session" in auth_client.cookies


def test_bearer_token_authenticates_reads_and_writes_without_csrf(
    auth_client: TestClient, db: Session
) -> None:
    make_user(db)
    token = _mobile_login(auth_client)
    auth = {"Authorization": f"Bearer {token}"}
    created = auth_client.post(
        f"{API}/opportunities", json={"company": "Acme", "role": "Dev"}, headers=auth
    )
    assert created.status_code == 201, created.text
    listed = auth_client.get(f"{API}/opportunities", headers=auth)
    assert [o["company"] for o in listed.json()] == ["Acme"]
    assert auth_client.get(f"{API}/auth/me", headers=auth).json()["user"]["email"] == (
        "alice@example.com"
    )


def test_wrong_or_missing_bearer_token_is_rejected(auth_client: TestClient, db: Session) -> None:
    make_user(db)
    _mobile_login(auth_client)
    bad = auth_client.get(f"{API}/opportunities", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    assert auth_client.get(f"{API}/opportunities").status_code == 401


def test_logout_revokes_the_bearer_token(auth_client: TestClient, db: Session) -> None:
    make_user(db)
    auth = {"Authorization": f"Bearer {_mobile_login(auth_client)}"}
    assert auth_client.post(f"{API}/auth/logout", headers=auth).status_code == 204
    assert auth_client.get(f"{API}/opportunities", headers=auth).status_code == 401


def test_cookie_sessions_still_require_csrf(auth_client: TestClient, db: Session) -> None:
    make_user(db)
    auth_client.post(f"{API}/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    response = auth_client.post(f"{API}/opportunities", json={"company": "A", "role": "B"})
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
