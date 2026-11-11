import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.auth import AuthToken
from app.models.enums import UserStatus
from app.models.user import User
from tests.auth_helpers import API, PASSWORD, Response, login, make_user, move_clock
from tests.conftest import FakeEmailSender

REGISTER = {
    "full_name": "Alice Walker",
    "email": "alice@example.com",
    "password": PASSWORD,
    "accept_terms": True,
}


def _register(client: TestClient, **overrides: object) -> Response:
    return client.post(f"{API}/auth/register", json={**REGISTER, **overrides})


class TestRegistration:
    def test_success_creates_an_unverified_user_and_sends_one_email(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        response = _register(auth_client)

        assert response.status_code == 201
        assert "verify" in response.json()["message"].lower()
        user = db.scalar(select(User).where(User.email == "alice@example.com"))
        assert user is not None
        assert user.email_verified is False
        assert user.terms_accepted_at is not None
        assert len(email_sender.of_kind("verify_email")) == 1
        assert email_sender.messages[0].to_email == "alice@example.com"

    def test_password_is_hashed_never_stored_or_returned(
        self, auth_client: TestClient, db: Session
    ) -> None:
        response = _register(auth_client)
        user = db.scalar(select(User).where(User.email == "alice@example.com"))
        assert user is not None and user.password_hash is not None
        assert user.password_hash.startswith("$argon2")
        assert PASSWORD not in user.password_hash
        assert PASSWORD not in response.text
        assert verify_password(PASSWORD, user.password_hash)

    def test_verification_token_is_stored_hashed_and_expires(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        _register(auth_client)
        raw = email_sender.token_in_last()
        stored = db.scalars(select(AuthToken)).all()
        assert [t.token_hash for t in stored if raw in t.token_hash] == []
        assert len(stored) == 1 and stored[0].used_at is None

    def test_email_is_normalised_and_duplicates_are_refused_case_insensitively(
        self, auth_client: TestClient
    ) -> None:
        assert _register(auth_client, email="  Alice@Example.COM ").status_code == 201
        duplicate = _register(auth_client, email="ALICE@example.com")
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "email_taken"

    def test_duplicate_of_an_existing_google_only_account_is_refused(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db, "alice@example.com", password=None)
        assert _register(auth_client).status_code == 409

    @pytest.mark.parametrize(
        "email", ["", "plainaddress", "a@b", "a b@example.com", "@example.com"]
    )
    def test_invalid_email(self, auth_client: TestClient, email: str) -> None:
        assert _register(auth_client, email=email).status_code == 422

    @pytest.mark.parametrize(
        ("password", "fragment"),
        [("short1", "at least"), ("onlyletterspassword", "number"), ("1234567890123", "letter")],
    )
    def test_weak_passwords_are_rejected_with_a_reason(
        self, auth_client: TestClient, password: str, fragment: str
    ) -> None:
        response = _register(auth_client, password=password)
        assert response.status_code == 422
        assert response.json()["code"] == "weak_password"
        assert fragment in response.json()["detail"]

    def test_password_containing_the_name_is_rejected(self, auth_client: TestClient) -> None:
        assert _register(auth_client, password="Walker-secret-99").status_code == 422

    def test_terms_must_be_accepted(self, auth_client: TestClient) -> None:
        assert _register(auth_client, accept_terms=False).status_code == 422

    def test_name_is_required_and_cleaned(self, auth_client: TestClient, db: Session) -> None:
        assert _register(auth_client, full_name="   ").status_code == 422
        assert _register(auth_client, full_name="Alice   Q.  Walker").status_code == 201
        user = db.scalar(select(User).where(User.email == "alice@example.com"))
        assert user is not None and user.full_name == "Alice Q. Walker"

    def test_unknown_fields_are_rejected(self, auth_client: TestClient) -> None:
        assert _register(auth_client, status="suspended").status_code == 422

    def test_registration_does_not_sign_you_in(self, auth_client: TestClient) -> None:
        _register(auth_client)
        assert "session" not in auth_client.cookies
        assert auth_client.get(f"{API}/auth/me").status_code == 401

    def test_a_mail_provider_failure_does_not_break_registration_or_leak(
        self,
        auth_client: TestClient,
        db: Session,
        email_sender: FakeEmailSender,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from app.emails.sender import EmailDeliveryError

        email_sender.fail_with = EmailDeliveryError("SendGrid returned HTTP 500")
        with caplog.at_level(logging.ERROR, logger="app.email"):
            response = _register(auth_client)
        assert response.status_code == 201
        assert "SendGrid" not in response.text
        assert db.scalar(select(User).where(User.email == "alice@example.com")) is not None
        assert any("email delivery failed" in r.getMessage() for r in caplog.records)

    def test_logs_never_contain_the_password_or_the_link_token(
        self,
        auth_client: TestClient,
        email_sender: FakeEmailSender,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            _register(auth_client)
        token = email_sender.token_in_last()
        logged = " ".join(r.getMessage() + str(r.__dict__) for r in caplog.records)
        assert PASSWORD not in logged
        assert token not in logged

    def test_signups_are_rate_limited_per_ip(self, auth_client: TestClient) -> None:
        for i in range(5):
            assert _register(auth_client, email=f"user{i}@example.com").status_code == 201
        blocked = _register(auth_client, email="user99@example.com")
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
        move_clock(auth_client, timedelta(hours=1, minutes=1))
        assert _register(auth_client, email="user99@example.com").status_code == 201


class TestLogin:
    def test_success_sets_a_secure_cookie_and_returns_the_user(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        response = login(auth_client)

        assert response.status_code == 200
        body = response.json()
        assert body["user"]["email"] == "alice@example.com"
        assert body["user"]["email_verified"] is True
        assert body["csrf_token"]
        assert "password_hash" not in response.text
        assert PASSWORD not in response.text
        cookie = response.headers["set-cookie"].lower()
        assert "session=" in cookie
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
        assert "path=/" in cookie

    def test_the_session_cookie_is_not_the_stored_value(
        self, auth_client: TestClient, db: Session
    ) -> None:
        from app.models.auth import UserSession

        make_user(db)
        login(auth_client)
        stored = db.scalars(select(UserSession)).one()
        assert auth_client.cookies["session"] != stored.token_hash
        assert auth_client.cookies["session"] not in stored.token_hash

    def test_wrong_password_and_unknown_email_look_identical(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        wrong = login(auth_client, password="Not-The-Password-1")
        unknown = login(auth_client, email="nobody@example.com")
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json()
        assert wrong.json()["code"] == "invalid_credentials"

    def test_email_is_case_insensitive(self, auth_client: TestClient, db: Session) -> None:
        make_user(db)
        assert login(auth_client, email="ALICE@Example.com").status_code == 200

    def test_unverified_accounts_cannot_sign_in(self, auth_client: TestClient, db: Session) -> None:
        make_user(db, verified=False)
        response = login(auth_client)
        assert response.status_code == 403
        assert response.json()["code"] == "email_not_verified"
        assert "session" not in auth_client.cookies

    def test_state_of_the_account_is_only_revealed_after_the_password_is_right(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db, verified=False)
        response = login(auth_client, password="Wrong-Password-1")
        assert response.json()["code"] == "invalid_credentials"

    def test_suspended_accounts_cannot_sign_in(self, auth_client: TestClient, db: Session) -> None:
        make_user(db, status=UserStatus.suspended)
        response = login(auth_client)
        assert response.status_code == 403
        assert response.json()["code"] == "account_suspended"

    def test_google_only_accounts_cannot_use_password_login(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db, password=None)
        assert login(auth_client).status_code == 401

    def test_records_last_login(self, auth_client: TestClient, db: Session) -> None:
        user = make_user(db)
        assert user.last_login_at is None
        login(auth_client)
        assert user.last_login_at is not None

    def test_brute_force_is_throttled_even_for_the_right_password(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        for _ in range(5):
            assert login(auth_client, password="Wrong-Password-1").status_code == 401
        locked = login(auth_client)  # the correct password, but the account is locked
        assert locked.status_code == 429
        assert locked.json()["code"] == "rate_limited"
        assert int(locked.headers["Retry-After"]) > 0

        move_clock(auth_client, timedelta(minutes=16))
        assert login(auth_client).status_code == 200

    def test_success_resets_the_failure_counter(self, auth_client: TestClient, db: Session) -> None:
        make_user(db)
        for _ in range(4):
            login(auth_client, password="Wrong-Password-1")
        assert login(auth_client).status_code == 200
        for _ in range(4):
            assert login(auth_client, password="Wrong-Password-1").status_code == 401

    def test_throttling_one_account_does_not_lock_another(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db, "alice@example.com")
        make_user(db, "bob@example.com", name="Bob Stone")
        for _ in range(5):
            login(auth_client, "alice@example.com", "Wrong-Password-1")
        assert login(auth_client, "bob@example.com").status_code == 200

    def test_a_new_login_issues_a_new_session_id(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        login(auth_client)
        first = auth_client.cookies["session"]
        login(auth_client)
        assert auth_client.cookies["session"] != first
