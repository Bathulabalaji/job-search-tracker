import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.deps import get_clock
from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Wednesday 2026-11-11 10:00 IST. Fixed so working-day maths is deterministic.
NOW = datetime(2026, 11, 11, 4, 30, tzinfo=UTC)


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = make_url(get_settings().database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


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
    """Each test runs in a transaction that is rolled back, even though services call commit()."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None, timezone="Asia/Kolkata", followup_working_days=2, ghost_after_days=21
    )


@pytest.fixture
def clock(settings: Settings) -> Clock:
    return Clock(tz=ZoneInfo(settings.timezone), now_fn=lambda: NOW)


@pytest.fixture
def client(db: Session, clock: Clock) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_clock] = lambda: clock
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
