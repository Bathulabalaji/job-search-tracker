from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.auth import AuthToken, UserSession
from app.models.enums import AuthTokenPurpose
from tests.auth_helpers import API, PASSWORD, Response, login, make_user, move_clock, sign_in
from tests.conftest import FakeEmailSender, FakeGoogleVerifier

NEW_PASSWORD = "Another-Secret-77"


def _request_verification(client: TestClient, email: str = "alice@example.com") -> None:
    client.post(f"{API}/auth/resend-verification", json={"email": email})


class TestEmailVerification:
    def test_the_link_verifies_the_account_and_allows_sign_in(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        user = make_user(db, verified=False)
        _request_verification(auth_client)
        token = email_sender.token_in_last()

        response = auth_client.post(f"{API}/auth/verify-email", json={"token": token})

        assert response.status_code == 200
        assert user.email_verified is True
        assert login(auth_client).status_code == 200

    def test_the_email_links_to_the_frontend_with_the_token_in_the_fragment(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db, verified=False)
        _request_verification(auth_client)
        message = email_sender.messages[-1]
        assert "http://localhost:5173/verify-email#token=" in message.text
        assert "http://localhost:5173/verify-email#token=" in message.html
        assert "?token=" not in message.text  # query strings end up in server logs and referrers

    def test_a_token_cannot_be_used_twice(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db, verified=False)
        _request_verification(auth_client)
        token = email_sender.token_in_last()
        assert (
            auth_client.post(f"{API}/auth/verify-email", json={"token": token}).status_code == 200
        )

        again = auth_client.post(f"{API}/auth/verify-email", json={"token": token})
        assert again.status_code == 400
        assert again.json()["code"] == "token_used"

    def test_an_expired_token_is_refused(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        user = make_user(db, verified=False)
        _request_verification(auth_client)
        token = email_sender.token_in_last()

        move_clock(auth_client, timedelta(hours=24, minutes=1))
        response = auth_client.post(f"{API}/auth/verify-email", json={"token": token})

        assert response.status_code == 400
        assert response.json()["code"] == "token_expired"
        assert user.email_verified is False

    def test_a_token_still_works_just_before_it_expires(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db, verified=False)
        _request_verification(auth_client)
        move_clock(auth_client, timedelta(hours=23, minutes=59))
        response = auth_client.post(
            f"{API}/auth/verify-email", json={"token": email_sender.token_in_last()}
        )
        assert response.status_code == 200

    def test_unknown_or_malformed_tokens_are_refused(self, auth_client: TestClient) -> None:
        unknown = auth_client.post(f"{API}/auth/verify-email", json={"token": "x" * 43})
        assert unknown.status_code == 400
        assert unknown.json()["code"] == "invalid_token"
        assert auth_client.post(f"{API}/auth/verify-email", json={"token": "x"}).status_code == 422

    def test_a_reset_token_cannot_verify_an_email(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db, verified=False)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        token = email_sender.token_in_last()
        response = auth_client.post(f"{API}/auth/verify-email", json={"token": token})
        assert response.json()["code"] == "invalid_token"

    def test_resend_replaces_the_previous_link(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db, verified=False)
        _request_verification(auth_client)
        old = email_sender.token_in_last()
        _request_verification(auth_client)
        new = email_sender.token_in_last()

        assert old != new
        assert auth_client.post(f"{API}/auth/verify-email", json={"token": old}).status_code == 400
        assert auth_client.post(f"{API}/auth/verify-email", json={"token": new}).status_code == 200

    def test_resend_answers_identically_for_unknown_and_known_emails(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db, verified=False)
        known = auth_client.post(
            f"{API}/auth/resend-verification", json={"email": "alice@example.com"}
        )
        unknown = auth_client.post(
            f"{API}/auth/resend-verification", json={"email": "ghost@example.com"}
        )
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()
        assert len(email_sender.messages) == 1  # only the real account got mail

    def test_resend_sends_nothing_to_an_already_verified_account(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db)
        _request_verification(auth_client)
        assert email_sender.messages == []

    def test_resend_is_rate_limited_per_address(self, auth_client: TestClient, db: Session) -> None:
        make_user(db, verified=False)
        statuses = [
            auth_client.post(
                f"{API}/auth/resend-verification", json={"email": "alice@example.com"}
            ).status_code
            for _ in range(4)
        ]
        assert statuses == [202, 202, 202, 429]

    def test_verification_attempts_are_rate_limited(self, auth_client: TestClient) -> None:
        for _ in range(30):
            auth_client.post(f"{API}/auth/verify-email", json={"token": "y" * 43})
        assert (
            auth_client.post(f"{API}/auth/verify-email", json={"token": "y" * 43}).status_code
            == 429
        )


class TestForgotAndResetPassword:
    def test_reveals_nothing_about_which_emails_exist(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db)
        known = auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        unknown = auth_client.post(
            f"{API}/auth/forgot-password", json={"email": "ghost@example.com"}
        )
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()
        assert [m.to_email for m in email_sender.messages] == ["alice@example.com"]

    def test_full_reset_flow(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        user = make_user(db)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        message = email_sender.messages[-1]
        assert message.kind == "reset_password"
        assert "/reset-password#token=" in message.text

        response = auth_client.post(
            f"{API}/auth/reset-password",
            json={"token": email_sender.token_in_last(), "password": NEW_PASSWORD},
        )

        assert response.status_code == 200
        assert verify_password(NEW_PASSWORD, user.password_hash)
        assert login(auth_client, password=PASSWORD).status_code == 401  # old password is dead
        assert login(auth_client, password=NEW_PASSWORD).status_code == 200
        assert email_sender.of_kind("password_changed")  # security notification

    def test_a_reset_token_is_single_use(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        token = email_sender.token_in_last()
        body = {"token": token, "password": NEW_PASSWORD}
        assert auth_client.post(f"{API}/auth/reset-password", json=body).status_code == 200
        again = auth_client.post(
            f"{API}/auth/reset-password", json={"token": token, "password": "Third-Secret-55"}
        )
        assert again.status_code == 400
        assert again.json()["code"] == "token_used"

    def test_an_expired_reset_link_is_refused(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        user = make_user(db)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        token = email_sender.token_in_last()
        move_clock(auth_client, timedelta(minutes=31))

        response = auth_client.post(
            f"{API}/auth/reset-password", json={"token": token, "password": NEW_PASSWORD}
        )

        assert response.status_code == 400
        assert response.json()["code"] == "token_expired"
        assert verify_password(PASSWORD, user.password_hash)

    def test_a_weak_new_password_does_not_use_up_the_link(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        token = email_sender.token_in_last()

        weak = auth_client.post(
            f"{API}/auth/reset-password", json={"token": token, "password": "short1"}
        )
        assert weak.status_code == 422
        assert weak.json()["code"] == "weak_password"

        ok = auth_client.post(
            f"{API}/auth/reset-password", json={"token": token, "password": NEW_PASSWORD}
        )
        assert ok.status_code == 200

    def test_requesting_another_link_cancels_the_first(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        old = email_sender.token_in_last()
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        new = email_sender.token_in_last()
        body = {"password": NEW_PASSWORD}
        assert (
            auth_client.post(f"{API}/auth/reset-password", json={"token": old, **body}).status_code
            == 400
        )
        assert (
            auth_client.post(f"{API}/auth/reset-password", json={"token": new, **body}).status_code
            == 200
        )

    def test_the_link_can_be_checked_without_using_it_up(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        token = email_sender.token_in_last()

        for _ in range(3):  # checking is repeatable
            assert (
                auth_client.post(
                    f"{API}/auth/reset-password/check", json={"token": token}
                ).status_code
                == 200
            )
        done = auth_client.post(
            f"{API}/auth/reset-password", json={"token": token, "password": NEW_PASSWORD}
        )
        assert done.status_code == 200
        used = auth_client.post(f"{API}/auth/reset-password/check", json={"token": token})
        assert used.status_code == 400
        assert used.json()["code"] == "token_used"

    def test_checking_reports_expired_and_unknown_links(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        token = email_sender.token_in_last()
        unknown = auth_client.post(f"{API}/auth/reset-password/check", json={"token": "z" * 43})
        assert unknown.json()["code"] == "invalid_token"

        move_clock(auth_client, timedelta(minutes=31))
        expired = auth_client.post(f"{API}/auth/reset-password/check", json={"token": token})
        assert expired.json()["code"] == "token_expired"

    def test_a_verification_token_does_not_pass_the_reset_check(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db, verified=False)
        _request_verification(auth_client)
        response = auth_client.post(
            f"{API}/auth/reset-password/check", json={"token": email_sender.token_in_last()}
        )
        assert response.json()["code"] == "invalid_token"

    def test_checking_is_rate_limited(self, auth_client: TestClient) -> None:
        for _ in range(30):
            auth_client.post(f"{API}/auth/reset-password/check", json={"token": "y" * 43})
        blocked = auth_client.post(f"{API}/auth/reset-password/check", json={"token": "y" * 43})
        assert blocked.status_code == 429

    def test_resetting_signs_out_every_existing_session(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db)
        sign_in(auth_client)
        assert auth_client.get(f"{API}/auth/me").status_code == 200

        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        auth_client.post(
            f"{API}/auth/reset-password",
            json={"token": email_sender.token_in_last(), "password": NEW_PASSWORD},
        )

        assert auth_client.get(f"{API}/auth/me").status_code == 401
        assert all(s.revoked_at is not None for s in db.scalars(select(UserSession)))

    def test_resetting_also_verifies_an_unverified_email(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        user = make_user(db, verified=False)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        auth_client.post(
            f"{API}/auth/reset-password",
            json={"token": email_sender.token_in_last(), "password": NEW_PASSWORD},
        )
        assert user.email_verified is True

    def test_google_only_accounts_can_set_a_password_through_reset(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        user = make_user(db, password=None)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        auth_client.post(
            f"{API}/auth/reset-password",
            json={"token": email_sender.token_in_last(), "password": NEW_PASSWORD},
        )
        assert user.password_hash is not None
        assert login(auth_client, password=NEW_PASSWORD).status_code == 200

    def test_suspended_accounts_get_no_reset_email(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        from app.models.enums import UserStatus

        make_user(db, status=UserStatus.suspended)
        response = auth_client.post(
            f"{API}/auth/forgot-password", json={"email": "alice@example.com"}
        )
        assert response.status_code == 202
        assert email_sender.messages == []

    def test_tokens_are_stored_hashed(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        make_user(db)
        auth_client.post(f"{API}/auth/forgot-password", json={"email": "alice@example.com"})
        raw = email_sender.token_in_last()
        row = db.scalars(
            select(AuthToken).where(AuthToken.purpose == AuthTokenPurpose.reset_password)
        ).one()
        assert raw != row.token_hash and raw not in row.token_hash

    def test_forgot_password_is_rate_limited(self, auth_client: TestClient, db: Session) -> None:
        make_user(db)
        statuses = [
            auth_client.post(
                f"{API}/auth/forgot-password", json={"email": "alice@example.com"}
            ).status_code
            for _ in range(4)
        ]
        assert statuses == [202, 202, 202, 429]


class TestChangePasswordAndProfile:
    def test_change_password_signs_out_other_devices_but_not_this_one(
        self, auth_client: TestClient, db: Session, email_sender: FakeEmailSender
    ) -> None:
        user = make_user(db)
        headers = sign_in(auth_client)
        this_cookie = auth_client.cookies["session"]
        # A second device:
        other = TestClient(auth_client.app, base_url="http://localhost:5173")
        other_headers = sign_in(other)
        assert other.get(f"{API}/auth/me", headers=other_headers).status_code == 200

        response = auth_client.post(
            f"{API}/auth/change-password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers=headers,
        )

        assert response.status_code == 200
        assert verify_password(NEW_PASSWORD, user.password_hash)
        assert auth_client.cookies["session"] == this_cookie
        assert auth_client.get(f"{API}/auth/me").status_code == 200
        assert other.get(f"{API}/auth/me").status_code == 401
        assert email_sender.of_kind("password_changed")

    def test_the_current_password_must_be_right_and_that_is_not_a_401(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        headers = sign_in(auth_client)
        response = auth_client.post(
            f"{API}/auth/change-password",
            json={"current_password": "Wrong-Password-1", "new_password": NEW_PASSWORD},
            headers=headers,
        )
        # 400, not 401: the frontend treats 401 as "session expired" and signs the user out.
        assert response.status_code == 400
        assert response.json()["code"] == "incorrect_password"

    def test_guessing_the_current_password_is_throttled(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        headers = sign_in(auth_client)
        body = {"current_password": "Wrong-Password-1", "new_password": NEW_PASSWORD}
        for _ in range(5):
            auth_client.post(f"{API}/auth/change-password", json=body, headers=headers)
        assert (
            auth_client.post(f"{API}/auth/change-password", json=body, headers=headers).status_code
            == 429
        )

    def test_weak_and_unchanged_passwords_are_refused(
        self, auth_client: TestClient, db: Session
    ) -> None:
        make_user(db)
        headers = sign_in(auth_client)

        def change(new: str) -> Response:
            return auth_client.post(
                f"{API}/auth/change-password",
                json={"current_password": PASSWORD, "new_password": new},
                headers=headers,
            )

        assert change("short1").json()["code"] == "weak_password"
        assert change(PASSWORD).json()["code"] == "password_reused"

    def test_accounts_without_a_password_are_pointed_to_reset(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        from tests.test_helpers_google import sign_in_with_google

        headers = sign_in_with_google(auth_client, google, email="gina@example.com")
        response = auth_client.post(
            f"{API}/auth/change-password",
            json={"current_password": "anything-1", "new_password": NEW_PASSWORD},
            headers=headers,
        )
        assert response.status_code == 400
        assert response.json()["code"] == "no_password"

    def test_update_profile(self, auth_client: TestClient, db: Session) -> None:
        user = make_user(db)
        headers = sign_in(auth_client)
        response = auth_client.patch(
            f"{API}/auth/me", json={"full_name": "  Alice   B. Walker "}, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "Alice B. Walker"
        assert user.full_name == "Alice B. Walker"

    def test_profile_cannot_change_email_or_status(
        self, auth_client: TestClient, db: Session
    ) -> None:
        user = make_user(db)
        headers = sign_in(auth_client)
        response = auth_client.patch(
            f"{API}/auth/me",
            json={"full_name": "Alice", "email": "evil@example.com", "status": "active"},
            headers=headers,
        )
        assert response.status_code == 422
        assert user.email == "alice@example.com"
