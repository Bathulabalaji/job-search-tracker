from datetime import timedelta

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_deps import client_ip
from app.core.config import Settings
from app.main import app
from app.models.auth import UserSession
from app.models.enums import UserStatus
from tests.auth_helpers import API, login, make_user, move_clock, sign_in

OPPORTUNITY = {"company": "Acme", "role": "Dev"}


class TestProtectedEndpoints:
    @pytest.mark.parametrize(
        "path",
        [
            "/opportunities",
            "/contacts",
            "/interactions",
            "/followups",
            "/daily-logs",
            "/daily-logs/streak",
            "/weekly-targets",
            "/prep-items",
            "/resumes",
            "/dashboard/today",
            "/dashboard/summary",
            "/analytics/weekly",
            "/auth/me",
        ],
    )
    def test_require_sign_in(self, auth_client: TestClient, path: str) -> None:
        response = auth_client.get(f"{API}{path}")
        assert response.status_code == 401
        assert response.json()["code"] == "not_authenticated"

    def test_health_stays_public(self, auth_client: TestClient) -> None:
        assert auth_client.get(f"{API}/health").status_code == 200

    def test_a_signed_in_user_can_use_the_api(self, auth_client: TestClient, db: Session) -> None:
        make_user(db)
        headers = sign_in(auth_client)
        created = auth_client.post(f"{API}/opportunities", json=OPPORTUNITY, headers=headers)
        assert created.status_code == 201
        assert auth_client.get(f"{API}/opportunities").json()[0]["company"] == "Acme"

    def test_a_forged_or_random_cookie_is_not_a_session(self, auth_client: TestClient) -> None:
        auth_client.cookies.set("session", "not-a-real-session-token")
        assert auth_client.get(f"{API}/auth/me").status_code == 401


class TestCsrfAndOrigin:
    def test_state_changing_requests_need_the_csrf_header(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        sign_in(auth_client)  # cookie is set, but we "forget" the header
        response = auth_client.post(f"{API}/opportunities", json=OPPORTUNITY)
        assert response.status_code == 403
        assert response.json()["code"] == "csrf_failed"

    def test_a_wrong_csrf_token_is_refused(self, auth_client: TestClient, db: Session) -> None:
        make_user(db)
        sign_in(auth_client)
        response = auth_client.post(
            f"{API}/opportunities", json=OPPORTUNITY, headers={"X-CSRF-Token": "guess"}
        )
        assert response.status_code == 403

    def test_a_csrf_token_from_another_session_is_refused(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        make_user(db, "bob@example.com", name="Bob Stone")
        bobs = TestClient(auth_client.app, base_url="http://localhost:5173")
        bobs_headers = sign_in(bobs, "bob@example.com")
        sign_in(auth_client)
        response = auth_client.post(f"{API}/opportunities", json=OPPORTUNITY, headers=bobs_headers)
        assert response.status_code == 403

    @pytest.mark.parametrize("method", ["patch", "delete"])
    def test_every_unsafe_method_is_covered(
        self, auth_client: TestClient, db: Session, method: str
    ) -> None:
        make_user(db)
        headers = sign_in(auth_client)
        created = auth_client.post(f"{API}/opportunities", json=OPPORTUNITY, headers=headers).json()
        url = f"{API}/opportunities/{created['id']}"
        kwargs = {"json": {"priority": 1}} if method == "patch" else {}
        assert getattr(auth_client, method)(url, **kwargs).status_code == 403
        assert getattr(auth_client, method)(url, headers=headers, **kwargs).status_code < 300

    def test_reads_do_not_need_the_header(self, auth_client: TestClient, db: Session) -> None:
        make_user(db)
        sign_in(auth_client)
        assert auth_client.get(f"{API}/opportunities").status_code == 200

    def test_csrf_token_is_stable_for_a_session_and_returned_by_me(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        headers = sign_in(auth_client)
        assert auth_client.get(f"{API}/auth/me").json()["csrf_token"] == headers["X-CSRF-Token"]

    def test_requests_from_another_origin_are_refused(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        response = auth_client.post(
            f"{API}/auth/login",
            json={"email": "alice@example.com", "password": "Correct-Horse-9"},
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "bad_origin"
        assert "session" not in auth_client.cookies

    def test_the_configured_origin_is_accepted(self, auth_client: TestClient, db: Session) -> None:
        make_user(db)
        response = auth_client.post(
            f"{API}/auth/login",
            json={"email": "alice@example.com", "password": "Correct-Horse-9"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 200

    def test_cors_allows_credentials_only_for_known_origins(self, auth_client: TestClient) -> None:
        good = auth_client.options(
            f"{API}/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        assert good.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert good.headers["access-control-allow-credentials"] == "true"
        assert "x-csrf-token" in good.headers["access-control-allow-headers"].lower()

        bad = auth_client.options(
            f"{API}/auth/login",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
        assert "access-control-allow-origin" not in bad.headers


class TestSessionLifecycle:
    def test_logout_revokes_the_session_server_side(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        headers = sign_in(auth_client)
        stolen_cookie = auth_client.cookies["session"]

        response = auth_client.post(f"{API}/auth/logout", headers=headers)

        assert response.status_code == 204
        assert "session" not in auth_client.cookies  # the browser forgets it...
        assert db.scalars(select(UserSession)).one().revoked_at is not None
        # ...and, more importantly, a copy of the old cookie no longer works anywhere.
        auth_client.cookies.set("session", stolen_cookie)
        assert auth_client.get(f"{API}/auth/me").status_code == 401

    def test_logout_without_a_session_is_harmless(self, auth_client: TestClient) -> None:
        assert auth_client.post(f"{API}/auth/logout").status_code == 204

    def test_logout_needs_the_csrf_header_when_signed_in(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        sign_in(auth_client)
        assert auth_client.post(f"{API}/auth/logout").status_code == 403

    def test_logout_everywhere(self, auth_client: TestClient, db: Session) -> None:
        make_user(db)
        headers = sign_in(auth_client)
        other = TestClient(auth_client.app, base_url="http://localhost:5173")
        sign_in(other)

        assert auth_client.post(f"{API}/auth/logout-all", headers=headers).status_code == 204
        assert other.get(f"{API}/auth/me").status_code == 401

    def test_sessions_expire_after_the_idle_window(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        sign_in(auth_client)
        move_clock(auth_client, timedelta(days=7, minutes=1))
        response = auth_client.get(f"{API}/auth/me")
        assert response.status_code == 401

    def test_activity_keeps_a_session_alive_but_not_past_the_absolute_limit(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        sign_in(auth_client)
        for day in range(5, 30, 5):  # touch it every 5 days: idle limit (7) never trips
            move_clock(auth_client, timedelta(days=day))
            assert auth_client.get(f"{API}/auth/me").status_code == 200
        move_clock(auth_client, timedelta(days=30, minutes=1))
        assert auth_client.get(f"{API}/auth/me").status_code == 401

    def test_suspending_an_account_ends_its_sessions_at_once(
        self, auth_client: TestClient, db: Session
    ) -> None:
        user = make_user(db)
        sign_in(auth_client)
        user.status = UserStatus.suspended
        db.flush()
        assert auth_client.get(f"{API}/auth/me").status_code == 401

    def test_me_returns_the_profile(self, auth_client: TestClient, db: Session) -> None:
        make_user(db)
        sign_in(auth_client)
        body = auth_client.get(f"{API}/auth/me").json()
        assert body["user"]["email"] == "alice@example.com"
        assert body["user"]["has_password"] is True
        assert body["user"]["google_linked"] is False
        assert "password_hash" not in str(body)

    def test_login_while_signed_in_does_not_reuse_the_old_session(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        login(auth_client)
        old = auth_client.cookies["session"]
        login(auth_client)
        assert auth_client.cookies["session"] != old


class TestHardening:
    def test_security_headers_on_every_response(self, auth_client: TestClient) -> None:
        response = auth_client.get(f"{API}/health")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"

    def test_auth_responses_are_never_cached(self, auth_client: TestClient) -> None:
        assert auth_client.get(f"{API}/auth/me").headers["cache-control"] == "no-store"

    def test_unexpected_errors_do_not_leak_internals(self, db: Session) -> None:
        from app.api.auth_deps import get_current_user
        from app.db.session import get_db

        def boom() -> None:
            raise RuntimeError("secret internal detail: postgres://user:pw@host/db")

        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = boom
        try:
            response = TestClient(app, raise_server_exceptions=False).get(f"{API}/opportunities")
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 500
        assert response.json() == {
            "detail": "Something went wrong. Please try again.",
            "code": "internal_error",
        }
        assert "postgres" not in response.text

    def test_sql_injection_attempts_are_just_strings(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        attack = "' OR '1'='1' --"
        assert login(auth_client, email="a@b.co", password=attack).status_code == 401
        headers = sign_in(auth_client)
        assert auth_client.get(f"{API}/opportunities", params={"q": attack}).status_code == 200
        created = auth_client.post(
            f"{API}/opportunities", json={"company": attack, "role": "x"}, headers=headers
        )
        assert created.status_code == 201
        assert created.json()["company"] == attack


class TestClientIp:
    def _request(self, headers: dict[str, str], host: str = "10.0.0.1") -> Request:
        scope = {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (host, 1234),
        }
        return Request(scope)

    def test_forwarded_header_is_ignored_unless_a_proxy_is_trusted(
        self, settings: Settings
    ) -> None:
        request = self._request({"X-Forwarded-For": "1.2.3.4"})
        assert client_ip(request, settings) == "10.0.0.1"

    def test_with_one_trusted_proxy_the_last_entry_wins_and_spoofing_is_useless(
        self, settings: Settings
    ) -> None:
        trusted = settings.model_copy(update={"trusted_proxy_count": 1})
        request = self._request({"X-Forwarded-For": "6.6.6.6, 203.0.113.9"})
        assert client_ip(request, trusted) == "203.0.113.9"

    def test_falls_back_to_the_socket_when_the_header_is_short(self, settings: Settings) -> None:
        trusted = settings.model_copy(update={"trusted_proxy_count": 2})
        assert client_ip(self._request({"X-Forwarded-For": "1.1.1.1"}), trusted) == "10.0.0.1"
