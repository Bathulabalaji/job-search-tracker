"""Replay the golden conversations in evals/golden against the real graph, with scripted models."""

import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from langchain_core.messages import AIMessage
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_active_checker, get_job_search_providers
from app.llm.errors import RateLimited
from app.llm.providers.fake import FakeCall, FakeProvider, FakeStep
from app.main import app
from app.models.opportunity import Opportunity
from tests.assistant.conftest import ChatHarness
from tests.assistant.test_chat_api import tool_call, verdict
from tests.jobsearch.helpers import FakeChecker, FakeJobProvider, hit

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden"
CASES = sorted(GOLDEN.glob("*.yaml"))


def load(path: Path) -> dict[str, Any]:
    case = yaml.safe_load(path.read_text())
    assert isinstance(case, dict) and case.get("name") == path.stem, f"{path.name}: bad name"
    assert case.get("turns"), f"{path.name}: no turns"
    return case


def script(provider: FakeProvider, steps: list[dict[str, Any]], opp_ids: dict[str, int]) -> None:
    for step in steps:
        ((kind, value),) = step.items()
        if kind == "verdict":
            provider.script(verdict(value["intent"], value.get("in_scope", True)))
        elif kind == "tool_call":
            args = {
                k: (opp_ids[v[5:-1]] if isinstance(v, str) and v.startswith("{opp:") else v)
                for k, v in (value.get("args") or {}).items()
            }
            provider.script(tool_call(value["name"], args))
        elif kind == "reply":
            provider.script(AIMessage(content=value))
        elif kind == "error":
            ((_, window),) = value.items()
            provider.script(FakeStep(error=RateLimited("busy", kind=window)))
        else:
            raise AssertionError(f"unknown step {kind!r}")


@pytest.fixture
def jobs_api() -> Iterator[list[FakeJobProvider]]:
    providers: list[FakeJobProvider] = []
    app.dependency_overrides[get_job_search_providers] = lambda: providers
    app.dependency_overrides[get_active_checker] = lambda: FakeChecker()
    yield providers


def all_calls(chat: ChatHarness) -> list[FakeCall]:
    return [*chat.groq.calls, *chat.google.calls]


def sent_text(call: FakeCall) -> list[str]:
    return [str(m.content) for m in call.messages]


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_golden_conversation(
    path: Path, chat: ChatHarness, db: Session, jobs_api: list[FakeJobProvider]
) -> None:
    case = load(path)
    opp_ids: dict[str, int] = {}
    for opp in (case.get("seed") or {}).get("opportunities", []):
        created = chat.client.post("/api/v1/opportunities", json=opp)
        assert created.status_code == 201, created.text
        opp_ids[opp["company"]] = int(created.json()["id"])
    for contact in (case.get("seed") or {}).get("contacts", []):
        made = chat.client.post(
            "/api/v1/contacts",
            json={**contact, "opportunity_id": opp_ids[contact.pop("opportunity")]},
        )
        assert made.status_code == 201, made.text
    if case.get("jobs"):
        jobs_api.append(
            FakeJobProvider("serpapi", [hit(j["company"], j["title"]) for j in case["jobs"]])
        )
    conversation = chat.client.post("/api/v1/chat/conversations", json={}).json()["id"]
    writes_before = db.scalar(select(func.count()).select_from(Opportunity))

    for turn in case["turns"]:
        calls_before = len(all_calls(chat))
        script(chat.groq, turn.get("groq", []), opp_ids)
        script(chat.google, turn.get("google", []), opp_ids)
        response = chat.client.post(
            f"/api/v1/chat/conversations/{conversation}/messages",
            json={"content": turn["say"], "client_message_id": str(uuid.uuid4())},
        )
        assert response.status_code == 200, response.text
        events = parse(response.text)
        check(chat, db, case, turn["expect"], events, all_calls(chat)[calls_before:], writes_before)


def parse(body: str) -> list[tuple[str, dict[str, Any]]]:
    from tests.assistant.conftest import parse_sse

    return parse_sse(body)


def check(
    chat: ChatHarness,
    db: Session,
    case: dict[str, Any],
    expect: dict[str, Any],
    events: list[tuple[str, dict[str, Any]]],
    calls: list[FakeCall],
    writes_before: int | None,
) -> None:
    names = [n for n, _ in events]
    answer = "".join(str(d["delta"]) for n, d in events if n == "token")
    if "tools" in expect:
        assert [d["name"] for n, d in events if n == "tool_start"] == expect["tools"]
    for phrase in expect.get("contains", []):
        assert phrase in answer, f"{case['name']}: answer lacks {phrase!r}: {answer!r}"
    for phrase in expect.get("not_contains", []):
        assert phrase not in answer
    for event in expect.get("events", []):
        assert event in names, f"{case['name']}: no {event!r} event in {names}"
    for event in expect.get("no_events", []):
        assert event not in names, f"{case['name']}: unexpected {event!r} event"
    if "agent_calls" in expect:
        # Guardrail calls ask for a structured verdict; everything else is the agent.
        agent = [c for c in calls if c.schema is None]
        assert len(agent) == expect["agent_calls"], f"{case['name']}: {len(agent)} agent calls"
    for phrase in expect.get("never_sent_to_a_model", []):
        assert not any(phrase in t for c in calls for t in sent_text(c))
    for phrase in expect.get("wrapped_as_untrusted", []):
        carrying = [t for c in calls for t in sent_text(c) if phrase in t]
        assert carrying, f"{case['name']}: the phrase never reached a model, so nothing is proved"
        for text in carrying:
            for match in re.finditer(re.escape(phrase), text):
                before, after = text[: match.start()], text[match.end() :]
                assert before.rfind("<untrusted_content>") > before.rfind("</untrusted_content>")
                assert "</untrusted_content>" in after
    if expect.get("nothing_written"):
        assert db.scalar(select(func.count()).select_from(Opportunity)) == writes_before
        for opp in db.scalars(select(Opportunity)):
            assert opp.next_action is None
