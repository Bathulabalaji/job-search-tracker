"""Phase 5: visible quotas, the assistant opt-out, and what the logs must never contain."""

import logging
import uuid

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.resume import Resume
from tests.assistant.conftest import ChatHarness
from tests.assistant.pdf import RESUME_TEXT, make_pdf
from tests.assistant.test_chat_api import new_conversation, send, text_of, verdict
from tests.assistant.test_matching import JD, indexed_resume, opportunity
from tests.assistant.test_resume_documents import create_resume, upload

API = "/api/v1/chat"


def usage(chat: ChatHarness) -> dict[str, dict[str, object]]:
    rows = chat.client.get(f"{API}/usage").json()
    return {row["name"]: row for row in rows}


def test_usage_lists_every_allowance_and_counts_what_is_used(chat: ChatHarness) -> None:
    before = usage(chat)
    # job search isn't configured in this harness, so its allowances are not offered
    assert set(before) == {"messages", "matches", "polish", "reindex"}
    assert before["messages"]["limit"] == chat.settings.chat_daily_messages
    assert before["messages"]["used"] == 0 and before["messages"]["resets_at"] is None

    conversation_id = new_conversation(chat)
    chat.groq.script(verdict("smalltalk"), AIMessage(content="Hi!"))
    send(chat, conversation_id, "hello")
    after = usage(chat)
    assert after["messages"]["used"] == 1 and after["messages"]["resets_at"] is not None

    resume_id = create_resume(chat)
    chat.client.post(f"/api/v1/resumes/{resume_id}/document/process")  # no file: 404, not counted


def test_opting_out_turns_every_model_feature_off_for_that_user(chat: ChatHarness) -> None:
    resume_id = indexed_resume(chat)
    opp_id = opportunity(chat)
    conversation_id = new_conversation(chat)
    assert chat.client.get(f"{API}/config").json()["enabled"] is True

    off = chat.client.put(f"{API}/preferences", json={"assistant_opt_out": True})
    assert off.status_code == 200
    body = off.json()
    assert body["enabled"] is False and body["assistant_opt_out"] is True
    assert body["matching"] is False and body["recommendations"] is False

    refused = chat.client.post(
        f"{API}/conversations/{conversation_id}/messages",
        json={"content": "hi", "client_message_id": str(uuid.uuid4())},
    )
    assert refused.status_code == 403 and refused.json()["code"] == "assistant_opted_out"
    match = chat.client.post(f"/api/v1/opportunities/{opp_id}/match", json={})
    assert match.status_code == 403 and match.json()["code"] == "assistant_opted_out"
    refresh = chat.client.post("/api/v1/recommendations/refresh")
    assert refresh.status_code == 403
    assert resume_id  # the resume itself stays usable: only model features are off

    calls_before = len(chat.google.embed_calls)
    fresh = create_resume(chat, "Another")
    assert upload(chat, fresh, make_pdf([RESUME_TEXT])).status_code == 201
    assert len(chat.google.embed_calls) == calls_before  # nothing was sent to a model
    detail = chat.client.get(f"/api/v1/resumes/{fresh}").json()["document"]
    assert detail["embed_status"] == "none" and "switched the AI assistant off" in str(
        detail["processing_error"]
    )

    on = chat.client.put(f"{API}/preferences", json={"assistant_opt_out": False}).json()
    assert on["enabled"] is True and on["assistant_opt_out"] is False


def test_logs_carry_ids_and_sizes_never_what_the_user_wrote(
    chat: ChatHarness, caplog: pytest.LogCaptureFixture, db: Session
) -> None:
    secret_question = "Is ZEBRA-SECRET-PHRASE-42 a good reason to quit?"
    resume_secret = "UNICORN-RESUME-MARKER-77"
    caplog.set_level(logging.DEBUG)
    indexed_resume(chat, text=RESUME_TEXT + f"\nHobby: {resume_secret}")
    opportunity(chat, JD + " Secret-JD-WORD-99")
    conversation_id = new_conversation(chat)
    chat.groq.script(verdict("smalltalk"), AIMessage(content="Reply about ZEBRA-REPLY-55."))
    events = send(chat, conversation_id, secret_question)
    assert "ZEBRA-REPLY-55" in text_of(events)  # the reply reached the user...

    logged = "\n".join(
        record.getMessage() + " " + str(sorted(record.__dict__.items()))
        for record in caplog.records
    )
    assert "app.assistant" in logged or "llm_call" in logged  # ...and logging really ran
    for forbidden in (
        "ZEBRA-SECRET-PHRASE-42",
        "ZEBRA-REPLY-55",
        resume_secret,
        "Secret-JD-WORD-99",
    ):
        assert forbidden not in logged
    assert db.scalars(select(Resume)).first() is not None
