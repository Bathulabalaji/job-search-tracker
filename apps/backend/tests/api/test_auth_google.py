from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import AuthIdentity, UserSession
from app.models.enums import UserStatus
from app.models.user import User
from app.services.google_auth import GoogleAuthError
from tests.auth_helpers import API, PASSWORD, login, make_user, move_clock
from tests.conftest import FakeEmailSender, FakeGoogleVerifier
from tests.test_helpers_google import claims, get_nonce, google_login


def _user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


class TestGoogleSignUpAndIn:
    def test_a_new_google_user_gets_a_verified_account_without_a_password(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        response = google_login(auth_client, google, email="gina@example.com", name="Gina Google")

        assert response.status_code == 200
        body = response.json()
        assert body["is_new_user"] is True
        assert body["user"]["email"] == "gina@example.com"
        assert body["user"]["email_verified"] is True
        assert body["user"]["has_password"] is False
        assert body["user"]["google_linked"] is True
        assert "httponly" in response.headers["set-cookie"].lower()
        user = db.scalar(select(User).where(User.email == "gina@example.com"))
        assert user is not None and user.password_hash is None
        assert auth_client.get(f"{API}/auth/me").status_code == 200

    def test_signing_in_again_reuses_the_account(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        google_login(auth_client, google)
        before = _user_count(db)
        again = google_login(auth_client, google)
        assert again.status_code == 200
        assert again.json()["is_new_user"] is False
        assert _user_count(db) == before

    def test_the_stable_google_id_wins_over_the_email(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        google_login(auth_client, google, sub="sub-1", email="old@example.com")
        count = _user_count(db)
        response = google_login(auth_client, google, sub="sub-1", email="changed@example.com")
        assert response.status_code == 200
        assert response.json()["user"]["email"] == "old@example.com"
        assert _user_count(db) == count

    def test_a_verified_existing_account_is_linked_not_duplicated(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        user = make_user(db, "gina@example.com", name="Gina G")
        count = _user_count(db)

        response = google_login(auth_client, google, email="gina@example.com")

        assert response.status_code == 200
        assert response.json()["is_new_user"] is False
        assert response.json()["user"]["id"] == user.id
        assert _user_count(db) == count
        assert db.scalars(select(AuthIdentity)).one().user_id == user.id
        assert user.password_hash is not None  # a legitimate owner keeps their password
        assert login(auth_client, "gina@example.com", PASSWORD).status_code == 200

    def test_linking_an_unverified_account_discards_its_password(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        """Squatter registers victim@... with a password. When the real owner signs in with
        Google, the squatter's password must stop working."""
        squatted = make_user(db, "victim@example.com", verified=False, name="Squat Ter")
        response = google_login(auth_client, google, email="victim@example.com", name="Victim")

        assert response.status_code == 200
        assert response.json()["user"]["id"] == squatted.id
        assert squatted.password_hash is None
        assert squatted.email_verified is True
        other = TestClient(auth_client.app, base_url="http://localhost:5173")
        assert login(other, "victim@example.com", PASSWORD).status_code == 401

    def test_linking_signs_out_sessions_of_an_unverified_squatter(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        squatted = make_user(db, "victim@example.com", verified=False)
        from tests.conftest import NOW

        db.add(
            UserSession(
                user_id=squatted.id, token_hash="h" * 64, expires_at=NOW + timedelta(days=1)
            )
        )
        db.flush()
        google_login(auth_client, google, email="victim@example.com")
        old = db.scalars(select(UserSession).where(UserSession.token_hash == "h" * 64)).one()
        assert old.revoked_at is not None

    def test_the_google_name_is_used_and_falls_back_to_the_email(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        google_login(auth_client, google, email="noname@example.com", name=None, sub="s9")
        user = db.scalar(select(User).where(User.email == "noname@example.com"))
        assert user is not None and user.full_name == "noname"

    def test_google_email_is_normalised(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        make_user(db, "gina@example.com")
        count = _user_count(db)
        response = google_login(auth_client, google, email="Gina@Example.com")
        assert response.status_code == 200
        assert _user_count(db) == count


class TestGoogleRejections:
    def test_unverified_google_email_is_refused(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        response = google_login(auth_client, google, verified=False)
        assert response.status_code == 403
        assert response.json()["code"] == "google_email_unverified"
        assert db.scalar(select(User).where(User.email == "gina@example.com")) is None

    def test_a_token_google_rejects_is_refused(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        google.error = GoogleAuthError("token rejected: Token expired")
        nonce = get_nonce(auth_client)
        response = auth_client.post(
            f"{API}/auth/google", json={"credential": "x" * 30, "nonce": nonce}
        )
        assert response.status_code == 401
        assert response.json()["code"] == "google_auth_failed"
        assert "expired" not in response.text.lower()  # no verifier internals leak
        assert "session" not in auth_client.cookies

    def test_a_missing_or_forged_nonce_is_refused(
        self, auth_client: TestClient, google: FakeGoogleVerifier
    ) -> None:
        google.claims = claims(nonce="attacker-chosen-nonce")
        for nonce in ("attacker-chosen-nonce", "1.2.3.4.5.6.7.8", "x" * 20):
            response = auth_client.post(
                f"{API}/auth/google", json={"credential": "x" * 30, "nonce": nonce}
            )
            assert response.status_code == 401
        assert google.received == []  # never even asked Google

    def test_a_replayed_token_with_a_different_nonce_is_refused(
        self, auth_client: TestClient, google: FakeGoogleVerifier
    ) -> None:
        # The token was minted for a different sign-in attempt than the one we issued a nonce for.
        response = google_login(auth_client, google, token_nonce="some-other-nonce-value")
        assert response.status_code == 401

    def test_a_token_without_a_nonce_is_refused(
        self, auth_client: TestClient, google: FakeGoogleVerifier
    ) -> None:
        nonce = get_nonce(auth_client)
        google.claims = claims(nonce=None)
        response = auth_client.post(
            f"{API}/auth/google", json={"credential": "x" * 30, "nonce": nonce}
        )
        assert response.status_code == 401

    def test_an_old_nonce_is_refused(
        self, auth_client: TestClient, google: FakeGoogleVerifier
    ) -> None:
        nonce = get_nonce(auth_client)
        move_clock(auth_client, timedelta(minutes=11))
        response = google_login(auth_client, google, nonce=nonce)
        assert response.status_code == 401

    def test_suspended_accounts_cannot_use_google(
        self, auth_client: TestClient, db: Session, google: FakeGoogleVerifier
    ) -> None:
        make_user(db, "gina@example.com", status=UserStatus.suspended)
        response = google_login(auth_client, google, email="gina@example.com")
        assert response.status_code == 403
        assert response.json()["code"] == "account_suspended"
        assert "session" not in auth_client.cookies

    def test_the_frontend_cannot_supply_profile_data(
        self, auth_client: TestClient, google: FakeGoogleVerifier
    ) -> None:
        nonce = get_nonce(auth_client)
        google.claims = claims(nonce=nonce)
        response = auth_client.post(
            f"{API}/auth/google",
            json={"credential": "x" * 30, "nonce": nonce, "email": "admin@example.com"},
        )
        assert response.status_code == 422  # extra fields are not even accepted

    def test_google_attempts_are_rate_limited(
        self, auth_client: TestClient, google: FakeGoogleVerifier
    ) -> None:
        for _ in range(30):
            auth_client.post(f"{API}/auth/google", json={"credential": "x" * 30, "nonce": "n" * 12})
        blocked = auth_client.post(
            f"{API}/auth/google", json={"credential": "x" * 30, "nonce": "n" * 12}
        )
        assert blocked.status_code == 429

    def test_google_sign_in_sends_no_email(
        self,
        auth_client: TestClient,
        google: FakeGoogleVerifier,
        email_sender: FakeEmailSender,
    ) -> None:
        google_login(auth_client, google)
        assert email_sender.messages == []
