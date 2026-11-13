"""Phase 1b: changes the assistant proposes wait for a confirmation card."""

import uuid
from datetime import date
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.providers.fake import FakeCall
from app.models.chat import ChatRun
from app.models.chat_action import ChatPendingAction
from app.models.enums import FollowupStatus, InteractionType, Stage
from app.models.followup import Followup
from app.models.interaction import Interaction
from app.models.opportunity import Opportunity
from tests.assistant.conftest import ChatHarness, parse_sse
from tests.assistant.test_chat_api import (
    API,
    names,
    new_conversation,
    send,
    text_of,
    tool_call,
    verdict,
)


def seed(db: Session) -> Opportunity:
    opp = Opportunity(
        user_id=db.info["user_id"], company="Zepto", role="Backend Engineer", stage=Stage.found
    )
    db.add(opp)
    db.flush()
    return opp


def detail(chat: ChatHarness, conversation_id: int) -> dict[str, Any]:
    response = chat.client.get(f"{API}/conversations/{conversation_id}")
    assert response.status_code == 200
    return dict(response.json())


def decide(
    chat: ChatHarness, conversation_id: int, action_id: str, decision: str, **edits: Any
) -> Any:
    body: dict[str, Any] = {"decision": decision}
    if edits:
        body["edits"] = edits
    return chat.client.post(f"{API}/conversations/{conversation_id}/actions/{action_id}", json=body)


def propose_move(
    chat: ChatHarness, db: Session, stage: str = "applied"
) -> tuple[int, dict[str, Any]]:
    opp = seed(db)
    chat.groq.script(
        verdict("write"),
        AIMessage(
            content="Sure, moving it.",
            tool_calls=[
                {
                    "name": "move_opportunity",
                    "id": "w1",
                    "args": {"opportunity_id": opp.id, "stage": stage},
                }
            ],
        ),
    )
    conversation_id = new_conversation(chat)
    events = send(chat, conversation_id, f"Move Zepto to {stage}")
    return conversation_id, dict(events)


def test_a_proposed_change_becomes_a_card_and_nothing_is_written(
    chat: ChatHarness, db: Session
) -> None:
    conversation_id, by_name = propose_move(chat, db)

    card = by_name["confirmation_required"]
    assert card["tool"] == "move_opportunity"
    assert card["title"] == "Move Zepto — Backend Engineer" and card["summary"] == "found → applied"
    assert [f["name"] for f in card["fields"]] == ["stage", "note"]
    assert by_name["done"]["status"] == "awaiting_confirmation"
    assert by_name["done"]["action_id"] == card["id"]
    assert "tool_end" not in by_name  # not executed
    assert db.scalars(select(Opportunity)).one().stage == Stage.found

    page = detail(chat, conversation_id)
    assert page["last_run"]["status"] == "awaiting_confirmation"
    assert (
        page["pending_action"]["id"] == card["id"] and page["pending_action"]["status"] == "pending"
    )
    reply = page["messages"][-1]
    assert reply["status"] == "awaiting" and reply["content"] == "Sure, moving it."

    busy = chat.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        json={"content": "and?", "client_message_id": str(uuid.uuid4())},
    )
    assert (busy.status_code, busy.json()["code"]) == (409, "action_pending")


def test_confirming_executes_once_through_the_service_and_continues_the_reply(
    chat: ChatHarness, db: Session
) -> None:
    conversation_id, by_name = propose_move(chat, db)
    action_id = by_name["confirmation_required"]["id"]

    def closing(call: FakeCall) -> AIMessage:
        tool = [m for m in call.messages if isinstance(m, ToolMessage)][-1]
        assert '"done":true' in str(tool.content)
        return AIMessage(content="Done: Zepto is now in applied.")

    chat.groq.script(closing)
    response = decide(chat, conversation_id, action_id, "confirm")
    assert response.status_code == 200
    events = parse_sse(response.text)
    by = dict(events)

    assert (
        by["tool_end"]["ok"] is True
        and by["tool_end"]["summary"] == "Zepto — Backend Engineer: found → applied"
    )
    assert set(by["tool_end"]["changed"]) >= {"opportunities", "followups", "interactions"}
    assert text_of(events).strip() == "Done: Zepto is now in applied."
    assert by["done"]["status"] == "completed" and "opportunities" in by["done"]["changed"]

    opp = db.scalars(select(Opportunity)).one()
    assert opp.stage == Stage.applied
    assert db.scalars(select(Interaction)).one().type == InteractionType.stage_change
    assert db.scalars(select(Followup)).one().status == FollowupStatus.pending  # auto-rule
    action = db.scalars(select(ChatPendingAction)).one()
    assert action.status == "executed" and action.result is not None
    assert str(action.result["summary"]).endswith("found → applied")

    page = detail(chat, conversation_id)
    reply = page["messages"][-1]
    assert reply["status"] == "complete"
    assert reply["content"] == "Sure, moving it.\n\nDone: Zepto is now in applied."
    assert reply["tool_calls"] == [
        {
            "name": "move_opportunity",
            "ok": True,
            "summary": "Zepto — Backend Engineer: found → applied",
        }
    ]
    assert page["pending_action"] is None and page["last_run"]["status"] == "completed"
    assert (
        chat.checkpointer.get_tuple({"configurable": {"thread_id": page["last_run"]["id"]}}) is None
    )

    again = decide(chat, conversation_id, action_id, "confirm")
    assert (again.status_code, again.json()["code"]) == (409, "action_already_decided")


def test_rejecting_writes_nothing_and_the_assistant_acknowledges(
    chat: ChatHarness, db: Session
) -> None:
    conversation_id, by_name = propose_move(chat, db)
    chat.groq.script(AIMessage(content="Okay, I left it as it was."))
    response = decide(chat, conversation_id, by_name["confirmation_required"]["id"], "reject")
    by = dict(parse_sse(response.text))
    assert by["tool_end"]["ok"] is False and by["tool_end"]["summary"] == "declined"
    assert db.scalars(select(Opportunity)).one().stage == Stage.found
    assert db.scalars(select(ChatPendingAction)).one().status == "rejected"
    last_call = chat.groq.calls[-1]
    assert "declined" in str(
        [m for m in last_call.messages if isinstance(m, ToolMessage)][-1].content
    )


def test_edits_change_the_executed_arguments_and_bad_edits_are_refused(
    chat: ChatHarness, db: Session
) -> None:
    conversation_id, by_name = propose_move(chat, db)
    action_id = by_name["confirmation_required"]["id"]
    bad = decide(chat, conversation_id, action_id, "confirm", stage="not-a-stage")
    assert (bad.status_code, bad.json()["code"]) == (422, "invalid_edits")
    sneaky = decide(chat, conversation_id, action_id, "confirm", opportunity_id=999)
    assert (sneaky.status_code, sneaky.json()["code"]) == (422, "invalid_edits")
    assert "opportunity_id" in sneaky.json()["detail"]

    chat.groq.script(AIMessage(content="Moved to screening."))
    good = decide(
        chat, conversation_id, action_id, "confirm", stage="screening", note="recruiter called"
    )
    assert good.status_code == 200
    assert db.scalars(select(Opportunity)).one().stage == Stage.screening
    assert "recruiter called" in str(db.scalars(select(Interaction)).one().summary)


def test_an_expired_card_cannot_be_confirmed_and_the_reply_is_closed(
    chat: ChatHarness, db: Session
) -> None:
    conversation_id, by_name = propose_move(chat, db)
    chat.clock.advance(minutes=16)
    response = decide(chat, conversation_id, by_name["confirmation_required"]["id"], "confirm")
    assert (response.status_code, response.json()["code"]) == (410, "action_expired")
    page = detail(chat, conversation_id)
    assert page["pending_action"] is None
    assert (
        page["last_run"]["status"] == "cancelled"
        and page["last_run"]["error_code"] == "action_expired"
    )
    assert "expired" in page["messages"][-1]["content"]
    assert db.scalars(select(Opportunity)).one().stage == Stage.found
    # The conversation is usable again.
    chat.groq.script(AIMessage(content="ok"))
    assert names(send(chat, conversation_id, "hello"))[-1] == "done"


def test_stop_while_a_card_is_up_declines_it(chat: ChatHarness, db: Session) -> None:
    conversation_id, by_name = propose_move(chat, db)
    run_id = by_name["run_started"]["run_id"]
    assert (
        chat.client.post(f"{API}/conversations/{conversation_id}/runs/{run_id}/cancel").status_code
        == 204
    )
    assert db.scalars(select(ChatPendingAction)).one().status == "rejected"
    assert db.scalars(select(ChatRun)).one().status == "cancelled"
    assert detail(chat, conversation_id)["pending_action"] is None


def test_a_change_to_someone_elses_data_never_gets_a_card(chat: ChatHarness, db: Session) -> None:
    chat.groq.script(
        verdict("write"),
        tool_call("move_opportunity", {"opportunity_id": 424242, "stage": "applied"}),
        AIMessage(content="I couldn't find that opportunity."),
    )
    events = send(chat, new_conversation(chat), "Move 424242 to applied")
    by = dict(events)
    assert "confirmation_required" not in by
    assert by["tool_end"]["ok"] is False and by["tool_end"]["summary"] == "not found"
    assert by["done"]["status"] == "completed"
    assert db.scalars(select(ChatPendingAction)).all() == []


def test_two_changes_in_one_turn_become_two_cards_in_sequence(
    chat: ChatHarness, db: Session
) -> None:
    opp = seed(db)
    chat.groq.script(
        verdict("write"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "move_opportunity",
                    "id": "a",
                    "args": {"opportunity_id": opp.id, "stage": "applied"},
                },
                {
                    "name": "add_followup",
                    "id": "b",
                    "args": {"opportunity_id": opp.id, "due_date": "2026-11-20", "channel": "call"},
                },
            ],
        ),
    )
    conversation_id = new_conversation(chat)
    first = dict(
        send(chat, conversation_id, "Move Zepto to applied and remind me Fri 20th by call")
    )
    assert first["confirmation_required"]["tool"] == "move_opportunity"

    second = dict(
        parse_sse(
            decide(chat, conversation_id, first["confirmation_required"]["id"], "confirm").text
        )
    )
    assert second["tool_end"]["summary"].endswith("found → applied")
    assert second["confirmation_required"]["tool"] == "add_followup"
    assert second["confirmation_required"]["summary"] == "call on Fri 20 Nov"
    assert second["done"]["status"] == "awaiting_confirmation"

    chat.groq.script(AIMessage(content="Both done."))
    third = parse_sse(
        decide(chat, conversation_id, second["confirmation_required"]["id"], "confirm").text
    )
    ends = [d for n, d in third if n == "tool_end"]
    assert [e["name"] for e in ends] == ["move_opportunity", "add_followup"]
    assert all(e["ok"] for e in ends)
    assert dict(third)["done"]["status"] == "completed"

    assert db.scalars(select(Opportunity)).one().stage == Stage.applied
    followups = db.scalars(select(Followup).order_by(Followup.id)).all()
    assert [f.due_date for f in followups] == [
        date(2026, 11, 13),
        date(2026, 11, 20),
    ]  # auto + asked
    assert len(db.scalars(select(Interaction)).all()) == 1  # the move happened exactly once
    actions = db.scalars(select(ChatPendingAction).order_by(ChatPendingAction.created_at)).all()
    assert [a.status for a in actions] == ["executed", "executed"]
    page = detail(chat, conversation_id)
    assert [t["name"] for t in page["messages"][-1]["tool_calls"]] == [
        "move_opportunity",
        "add_followup",
    ]


def test_writes_can_be_switched_off(chat: ChatHarness, db: Session) -> None:
    chat.settings.chat_writes_enabled = False
    seed(db)
    chat.groq.script(verdict("write"), AIMessage(content="You can do that on the Pipeline page."))
    events = send(chat, new_conversation(chat), "Move Zepto to applied")
    assert "confirmation_required" not in dict(events)
    agent_call = chat.groq.calls[1]
    assert all(getattr(t, "name", "") != "move_opportunity" for t in agent_call.tools)
    assert "cannot change anything" in str(agent_call.messages[0].content)


def test_the_stream_pings_while_the_model_is_slow(chat: ChatHarness) -> None:
    import time

    chat.settings.chat_heartbeat_seconds = 0.05

    def slow(call: FakeCall) -> AIMessage:
        time.sleep(0.25)
        return AIMessage(content="eventually")

    chat.groq.script(slow)
    conversation_id = new_conversation(chat)
    response = chat.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        json={"content": "hi", "client_message_id": str(uuid.uuid4())},
    )
    assert response.text.count(": ping") >= 2
    assert text_of(parse_sse(response.text)).strip() == "eventually"
