import uuid
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.graph import GuardrailVerdict
from app.assistant.prompts import DECLINE_MESSAGE
from app.llm.errors import RateLimited
from app.llm.providers.fake import FakeCall, FakeStep
from app.models.chat import ChatMessage, ChatRun
from app.models.enums import Stage
from app.models.opportunity import Opportunity
from app.models.user import User
from tests.assistant.conftest import ChatHarness, parse_sse

API = "/api/v1/chat"


def verdict(intent: str = "pipeline", in_scope: bool = True) -> FakeStep:
    return FakeStep(
        message=AIMessage(content="{}"), parsed=GuardrailVerdict(in_scope=in_scope, intent=intent)
    )


def tool_call(name: str, args: dict[str, Any] | None = None, call_id: str = "c1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": call_id}])


def new_conversation(chat: ChatHarness) -> int:
    response = chat.client.post(f"{API}/conversations", json={})
    assert response.status_code == 201
    return int(response.json()["id"])


def send(chat: ChatHarness, conversation_id: int, text: str) -> list[tuple[str, dict[str, Any]]]:
    response = chat.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        json={"content": text, "client_message_id": str(uuid.uuid4())},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_sse(response.text)


def names(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return [name for name, _ in events if name != "token"]


def text_of(events: list[tuple[str, dict[str, Any]]]) -> str:
    return "".join(str(data["delta"]) for name, data in events if name == "token")


def seed_opportunities(db: Session) -> None:
    for company, stage in [("Zepto", Stage.applied), ("Swiggy", Stage.interviewing)]:
        db.add(
            Opportunity(user_id=db.info["user_id"], company=company, role="Backend", stage=stage)
        )
    db.flush()


def test_a_turn_streams_tool_activity_and_the_answer_then_persists_it(
    chat: ChatHarness, db: Session
) -> None:
    seed_opportunities(db)
    chat.groq.script(
        verdict("pipeline"),
        tool_call("get_pipeline_summary"),
        AIMessage(content="You have 2 opportunities: one applied, one interviewing."),
    )
    conversation_id = new_conversation(chat)

    events = send(chat, conversation_id, "Summarise my pipeline")

    assert names(events) == ["run_started", "tool_start", "tool_end", "done"]
    tool_end = dict(events)["tool_end"]
    assert tool_end["name"] == "get_pipeline_summary" and tool_end["ok"] is True
    assert tool_end["summary"] == "2 opportunities"
    assert text_of(events).strip() == "You have 2 opportunities: one applied, one interviewing."
    # The second agent call saw the tool result, compacted.
    tool_messages = [m for m in chat.groq.calls[2].messages if isinstance(m, ToolMessage)]
    assert '"total":2' in str(tool_messages[0].content)

    detail = chat.client.get(f"{API}/conversations/{conversation_id}").json()
    assert detail["conversation"]["title"] == "Summarise my pipeline"
    user, assistant = detail["messages"]
    assert (user["role"], assistant["role"], assistant["status"]) == (
        "user",
        "assistant",
        "complete",
    )
    assert assistant["content"].startswith("You have 2 opportunities")
    assert assistant["tool_calls"] == [
        {"name": "get_pipeline_summary", "ok": True, "summary": "2 opportunities"}
    ]
    assert detail["last_run"]["status"] == "completed"
    assert (
        chat.checkpointer.get_tuple(  # completed runs leave no checkpoints behind
            {"configurable": {"thread_id": detail["last_run"]["id"]}}
        )
        is None
    )


def test_out_of_scope_questions_get_the_polite_decline_without_the_agent(chat: ChatHarness) -> None:
    chat.groq.script(verdict("out_of_scope", in_scope=False))
    conversation_id = new_conversation(chat)

    events = send(chat, conversation_id, "What's the capital of France?")

    assert text_of(events).strip() == DECLINE_MESSAGE
    assert len(chat.groq.calls) == 1  # the guardrail only
    assert chat.groq.calls[0].schema is GuardrailVerdict


def test_greetings_skip_the_guardrail_and_get_no_tools(chat: ChatHarness) -> None:
    chat.groq.script(AIMessage(content="Hi! Ask me about your job search."))
    events = send(chat, new_conversation(chat), "hello!")
    assert text_of(events).strip().startswith("Hi!")
    [call] = chat.groq.calls
    assert call.tools == []


def test_a_guardrail_outage_degrades_to_the_agent_with_a_notice(chat: ChatHarness) -> None:
    down = RateLimited("busy", kind="day")
    chat.groq.script(down)  # gpt-oss-20b
    chat.google.script(down, AIMessage(content="Here is your plan."))  # 3.5-lite guardrail, agent?
    chat.groq.script(AIMessage(content="Here is your plan."))
    events = send(chat, new_conversation(chat), "What should I do today?")
    assert ("notice", {"code": "guardrail_degraded"}) in events
    assert "Here is your plan." in text_of(events)


def test_capacity_failure_mid_run_resumes_without_repeating_the_tool(
    chat: ChatHarness, db: Session
) -> None:
    seed_opportunities(db)
    busy = RateLimited("tpm", kind="minute", retry_after=30)
    chat.groq.script(verdict("pipeline"), tool_call("get_pipeline_summary"), busy, busy)
    chat.google.script(busy, busy, busy)
    conversation_id = new_conversation(chat)

    events = send(chat, conversation_id, "Summarise my pipeline")

    assert names(events) == ["run_started", "tool_start", "tool_end", "error", "done"]
    error = dict(events)["error"]
    assert error["recoverable"] is True and error["code"] in ("assistant_capacity",)
    detail = chat.client.get(f"{API}/conversations/{conversation_id}").json()
    failed = detail["messages"][-1]
    assert failed["status"] == "failed" and "capacity" in failed["content"]
    run = detail["last_run"]
    assert run["status"] == "failed" and run["resumable"] is True

    # Later, budgets have recovered: resume continues from the checkpoint.
    chat.clock.advance(minutes=2)
    calls_before = len(chat.groq.calls)
    chat.groq.script(AIMessage(content="You have 2 opportunities."))
    resumed = chat.client.post(f"{API}/conversations/{conversation_id}/runs/{run['id']}/resume")
    assert resumed.status_code == 200
    resumed_events = parse_sse(resumed.text)

    assert "tool_start" not in names(resumed_events)  # the tool did not run again
    assert text_of(resumed_events).strip() == "You have 2 opportunities."
    [agent_call] = chat.groq.calls[calls_before:]
    assert any(isinstance(m, ToolMessage) for m in agent_call.messages)
    detail = chat.client.get(f"{API}/conversations/{conversation_id}").json()
    assert len(detail["messages"]) == 2  # the failed reply was replaced, not duplicated
    final = detail["messages"][-1]
    assert final["status"] == "complete" and final["content"] == "You have 2 opportunities."
    assert final["tool_calls"][0]["name"] == "get_pipeline_summary"
    assert detail["last_run"]["status"] == "completed"


def test_a_failed_tool_is_reported_to_the_model_not_the_user(chat: ChatHarness) -> None:
    def answer(call: FakeCall) -> AIMessage:
        tool = [m for m in call.messages if isinstance(m, ToolMessage)][0]
        assert "not found" in str(tool.content)
        return AIMessage(content="I couldn't find opportunity 999.")

    chat.groq.script(
        verdict("pipeline"), tool_call("get_opportunity", {"opportunity_id": 999}), answer
    )
    events = send(chat, new_conversation(chat), "Show opportunity 999")
    tool_end = dict(events)["tool_end"]
    assert (tool_end["ok"], tool_end["summary"]) == (False, "not found")
    assert "couldn't find" in text_of(events)


def test_one_run_at_a_time_and_messages_are_idempotent(chat: ChatHarness, db: Session) -> None:
    conversation_id = new_conversation(chat)
    chat.groq.script(AIMessage(content="ok"))
    body = {"content": "hi", "client_message_id": str(uuid.uuid4())}
    assert (
        chat.client.post(f"{API}/conversations/{conversation_id}/messages", json=body).status_code
        == 200
    )
    again = chat.client.post(f"{API}/conversations/{conversation_id}/messages", json=body)
    assert (again.status_code, again.json()["code"]) == (409, "duplicate_message")

    run = db.scalars(select(ChatRun)).one()
    run.status = "running"
    db.flush()
    busy = chat.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        json={"content": "next", "client_message_id": str(uuid.uuid4())},
    )
    assert (busy.status_code, busy.json()["code"]) == (409, "run_in_progress")
    chat.clock.advance(minutes=6)  # an orphaned run stops blocking the conversation
    chat.groq.script(AIMessage(content="ok"))
    assert (
        chat.client.post(
            f"{API}/conversations/{conversation_id}/messages",
            json={"content": "next", "client_message_id": str(uuid.uuid4())},
        ).status_code
        == 200
    )


def test_per_minute_quota_returns_429_with_retry_after(chat: ChatHarness) -> None:
    chat.settings.chat_per_minute = 1
    conversation_id = new_conversation(chat)
    chat.groq.script(AIMessage(content="ok"))
    send(chat, conversation_id, "hi")
    response = chat.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        json={"content": "hi again", "client_message_id": str(uuid.uuid4())},
    )
    assert response.status_code == 429
    assert response.json()["code"] == "chat_quota"
    assert int(response.headers["Retry-After"]) >= 1
    config = chat.client.get(f"{API}/config").json()
    assert config["enabled"] is True and config["messages_per_day"]["used"] == 1


def test_disabled_without_provider_keys(chat: ChatHarness) -> None:
    chat.settings.groq_api_key = ""
    chat.settings.google_ai_api_key = ""
    conversation_id = new_conversation(chat)
    assert chat.client.get(f"{API}/config").json()["enabled"] is False
    response = chat.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        json={"content": "hi", "client_message_id": str(uuid.uuid4())},
    )
    assert (response.status_code, response.json()["code"]) == (503, "assistant_disabled")


def test_other_users_conversations_are_invisible(chat: ChatHarness, db: Session) -> None:
    other = User(email="other@example.com", full_name="Other", status="active")
    db.add(other)
    db.flush()
    conversation_id = new_conversation(chat)
    db.info["user"] = other  # now acting as the other user
    assert chat.client.get(f"{API}/conversations/{conversation_id}").status_code == 404
    assert chat.client.get(f"{API}/conversations").json() == []
    response = chat.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        json={"content": "hi", "client_message_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_rename_archive_and_delete(chat: ChatHarness, db: Session) -> None:
    conversation_id = new_conversation(chat)
    chat.groq.script(AIMessage(content="ok"))
    send(chat, conversation_id, "hi")
    renamed = chat.client.patch(f"{API}/conversations/{conversation_id}", json={"title": "Plans"})
    assert renamed.json()["title"] == "Plans"
    chat.client.patch(f"{API}/conversations/{conversation_id}", json={"status": "archived"})
    assert chat.client.get(f"{API}/conversations").json() == []
    assert len(chat.client.get(f"{API}/conversations", params={"status": "archived"}).json()) == 1
    assert chat.client.delete(f"{API}/conversations/{conversation_id}").status_code == 204
    assert db.scalars(select(ChatMessage)).all() == []


def test_message_validation(chat: ChatHarness) -> None:
    conversation_id = new_conversation(chat)
    for content in ["   ", "x" * 2001]:
        response = chat.client.post(
            f"{API}/conversations/{conversation_id}/messages",
            json={"content": content, "client_message_id": str(uuid.uuid4())},
        )
        assert response.status_code == 422
