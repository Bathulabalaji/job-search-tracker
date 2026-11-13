import json
from collections.abc import Iterator
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.api.auth_deps import (
    get_checkpointer,
    get_clock,
    get_current_user,
    get_llm_providers,
    get_session_scope,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.llm.catalog import Provider
from app.llm.providers.fake import FakeProvider
from app.main import app
from tests.llm.helpers import MovableClock


@dataclass
class ChatHarness:
    client: TestClient
    groq: FakeProvider
    google: FakeProvider
    clock: MovableClock
    checkpointer: InMemorySaver
    settings: Settings


@pytest.fixture
def chat_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"groq_api_key": "test", "google_ai_api_key": "test"})


@pytest.fixture
def chat(db: Session, chat_settings: Settings) -> Iterator[ChatHarness]:
    clock = MovableClock()
    groq, google = FakeProvider("groq"), FakeProvider("google")
    saver = InMemorySaver()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_clock] = lambda: clock.clock
    app.dependency_overrides[get_settings] = lambda: chat_settings
    app.dependency_overrides[get_current_user] = lambda: db.info["user"]
    app.dependency_overrides[get_llm_providers] = lambda: {
        Provider.groq: groq,
        Provider.google: google,
    }
    app.dependency_overrides[get_session_scope] = lambda: lambda: nullcontext(db)
    app.dependency_overrides[get_checkpointer] = lambda: saver
    try:
        yield ChatHarness(TestClient(app), groq, google, clock, saver, chat_settings)
    finally:
        app.dependency_overrides.clear()


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.strip().split("\n\n"):
        name, data = "", ""
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        if name:
            events.append((name, json.loads(data)))
    return events
