import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.auth_deps import (
    get_clock,
    get_current_user,
    get_email_sender,
    get_google_verifier,
)
from app.core import security
from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.emails.sender import EmailMessage
from app.main import app
from app.models.enums import UserStatus
from app.models.user import User
from app.services.google_auth import GoogleAuthError, GoogleClaims

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Wednesday 2026-11-11 10:00 IST. Fixed so working-day maths is deterministic.
NOW = datetime(2026, 11, 11, 4, 30, tzinfo=UTC)

TEST_SECRET = "test-secret-key-that-is-definitely-long-enough"


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = make_url(get_settings().database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


@pytest.fixture(autouse=True, scope="session")
def _fast_password_hashing() -> None:
    """Argon2 at production cost makes every test that hashes a password take ~100ms."""
    security.set_hasher_for_tests(PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """A throwaway '<db>_test' database, rebuilt from the real Alembic migrations."""
    url = make_url(_test_database_url())
    assert url.database is not None and url.database.endswith("_test"), (
        "Refusing to wipe a database whose name does not end in '_test'"
    )

    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    test_engine = create_engine(url)
    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["database_url"] = url.render_as_string(hide_password=False)
    command.upgrade(cfg, "head")

    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Each test runs in a transaction that is rolled back, even though services call commit().

    Also creates the default signed-in user; its id is `db.info["user_id"]`, which the service
    tests pass to the services they build.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    default_user = User(
        email="default.user@example.com",
        full_name="Default User",
        status=UserStatus.active,
        email_verified_at=NOW,
    )
    session.add(default_user)
    session.flush()
    session.info["user_id"] = default_user.id
    session.info["user"] = default_user
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        timezone="Asia/Kolkata",
        followup_working_days=2,
        ghost_after_days=21,
        secret_key=TEST_SECRET,
        frontend_url="http://localhost:5173",
        cors_origins=["http://localhost:5173"],
        google_client_id="test-client-id.apps.googleusercontent.com",
    )


@pytest.fixture
def clock(settings: Settings) -> Clock:
    return Clock(tz=ZoneInfo(settings.timezone), now_fn=lambda: NOW)


@pytest.fixture
def client(db: Session, clock: Clock, settings: Settings) -> Iterator[TestClient]:
    """API client that is already signed in as the default user (auth bypassed).

    Use `auth_client` to exercise the real cookie, CSRF and session flow.
    """
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_current_user] = lambda: db.info["user"]
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---- Real authentication flow -------------------------------------------------------------------


class FakeEmailSender:
    """Captures outgoing email so tests can read the links without any network."""

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []
        self.fail_with: Exception | None = None

    def send(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.messages.append(message)

    def token_in_last(self) -> str:
        match = re.search(r"#token=([A-Za-z0-9_\-%]+)", self.messages[-1].text)
        assert match, "no token link in the last email"
        return match.group(1)

    def of_kind(self, kind: str) -> list[EmailMessage]:
        return [m for m in self.messages if m.kind == kind]


class FakeGoogleVerifier:
    """Stands in for Google. Tests set `claims` or `error` per scenario."""

    def __init__(self) -> None:
        self.claims: GoogleClaims | None = None
        self.error: GoogleAuthError | None = None
        self.received: list[str] = []

    def verify(self, credential: str) -> GoogleClaims:
        self.received.append(credential)
        if self.error is not None:
            raise self.error
        assert self.claims is not None, "test forgot to set Google claims"
        return self.claims


@pytest.fixture
def email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def google() -> FakeGoogleVerifier:
    return FakeGoogleVerifier()


@pytest.fixture
def auth_client(
    db: Session,
    settings: Settings,
    email_sender: FakeEmailSender,
    google: FakeGoogleVerifier,
) -> Iterator[TestClient]:
    """Unauthenticated client wired to fakes. Cookies persist between calls, like a browser."""
    now = {"value": NOW}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_clock] = lambda: Clock(
        tz=ZoneInfo(settings.timezone), now_fn=lambda: now["value"]
    )
    app.dependency_overrides[get_email_sender] = lambda: email_sender
    app.dependency_overrides[get_google_verifier] = lambda: google
    test_client = TestClient(app, base_url="http://localhost:5173")
    test_client.app_state_now = now  # type: ignore[attr-defined]  # lets tests move the clock
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
