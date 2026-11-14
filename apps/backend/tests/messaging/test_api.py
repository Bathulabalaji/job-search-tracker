"""Outreach messages over HTTP: profile, templates, drafts, suggestions, sent and replied."""

import uuid
from typing import Any

from langchain_core.messages import AIMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.providers.fake import FakeStep
from app.models.user import User
from app.services.messaging import Polished
from tests.assistant.conftest import ChatHarness
from tests.assistant.pdf import RESUME_TEXT, make_pdf
from tests.assistant.test_resume_documents import create_resume, script_profile, upload

M = "/api/v1/messages"
O = "/api/v1/opportunities"  # noqa: E741


def setup_job(chat: ChatHarness, *, stage: str = "applied") -> tuple[int, int]:
    """An opportunity (moved to `stage`) with one recruiter contact. Returns (opp, contact)."""
    opp = chat.client.post(
        O,
        json={"company": "Zepto", "role": "Backend Engineer", "stack_tags": ["python", "fastapi"]},
    ).json()
    if stage != "found":
        assert chat.client.post(f"{O}/{opp['id']}/move", json={"stage": stage}).status_code == 200
    contact = chat.client.post(
        "/api/v1/contacts",
        json={
            "opportunity_id": opp["id"], "name": "Riya Sharma", "role": "recruiter",
            "email": "riya@zepto.example", "linkedin_url": "https://linkedin.com/in/riya",
        },
    ).json()  # fmt: skip
    return int(opp["id"]), int(contact["id"])


def preview(chat: ChatHarness, opp: int, key: str, channel: str = "email", **extra: Any) -> Any:
    return chat.client.post(
        f"{O}/{opp}/messages/preview", json={"template_key": key, "channel": channel, **extra}
    )


def sent(chat: ChatHarness, opp: int, key: str, **extra: Any) -> Any:
    body = {"template_key": key, "channel": "email", "subject": "S", "body": "Hello", **extra}
    return chat.client.post(f"{O}/{opp}/messages/sent", json=body)


# ---- the sender -------------------------------------------------------------------------------


def test_profile_defaults_to_the_account_email_and_can_be_changed(
    chat: ChatHarness, db: Session
) -> None:
    first = chat.client.get(f"{M}/profile").json()
    assert first["from_email"] == db.get(User, db.info["user_id"]).email  # type: ignore[union-attr]
    assert first["india_style"] is True and first["proof_points"] == []

    saved = chat.client.put(
        f"{M}/profile",
        json={
            "from_email": "me@work.example", "headline": "a backend engineer with 4 years",
            "linkedin_url": "https://linkedin.com/in/me", "proof_points": ["Cut API latency 40%."],
            "notice_period": "30 days", "expected_ctc": "24 LPA",
        },
    ).json()  # fmt: skip
    assert saved["from_email"] == "me@work.example" and saved["notice_period"] == "30 days"
    cleared = chat.client.put(f"{M}/profile", json={"notice_period": ""}).json()
    assert cleared["notice_period"] is None and cleared["from_email"] == "me@work.example"


def test_profile_input_is_validated_and_cleaned(chat: ChatHarness) -> None:
    for bad in (
        {"from_email": "not-an-email"},
        {"linkedin_url": "javascript:alert(1)"},
        {"linkedin_url": "linkedin.com/in/me"},
        {"proof_points": ["a", "b", "c", "d"]},
        {"headline": "x" * 301},
        {"unknown": 1},
    ):
        assert chat.client.put(f"{M}/profile", json=bad).status_code == 422, bad
    ok = chat.client.put(f"{M}/profile", json={"headline": "a dev\x00 with\n skills"})
    assert ok.status_code == 200 and ok.json()["headline"] == "a dev with skills"


def test_headline_is_offered_from_the_resume(chat: ChatHarness) -> None:
    rid = create_resume(chat)
    script_profile(chat)
    assert upload(chat, rid, make_pdf([RESUME_TEXT])).status_code == 201
    suggested = chat.client.get(f"{M}/profile").json()["suggested_headline"]
    assert suggested and "4" in suggested and "engineer" in suggested.lower()


# ---- templates --------------------------------------------------------------------------------


def test_the_built_in_library_and_the_india_switch(chat: ChatHarness) -> None:
    keys = {t["key"] for t in chat.client.get(f"{M}/templates").json()}
    assert len(keys) == 14 and "sys:share_details" in keys and "sys:follow_up_1" in keys
    chat.client.put(f"{M}/profile", json={"india_style": False})
    keys = {t["key"] for t in chat.client.get(f"{M}/templates").json()}
    assert "sys:share_details" not in keys and len(keys) == 13


def test_custom_templates_are_validated(chat: ChatHarness) -> None:
    def create(**kw: Any) -> Any:
        body = {
            "name": "Mine",
            "channel": "email",
            "subject": "Hi {{company}}",
            "body": "Hello {{recipient_first}}",
        }
        return chat.client.post(f"{M}/templates", json={**body, **kw})

    assert create().status_code == 201
    assert create(body="Hi {{nonsense}}").json()["code"] == "unknown_field"
    assert create(body="Hi {{?proof_point}} no end").json()["code"] == "bad_template"
    assert create(subject=None).json()["code"] == "subject_required"
    assert create(channel="linkedin").json()["code"] == "subject_not_allowed"
    assert create(name="").status_code == 422 and create(body="x" * 3001).status_code == 422
    chat.settings.message_templates_max = 2
    assert create().status_code == 201
    assert create().json()["code"] == "template_limit"


def test_editing_a_built_in_makes_a_copy_and_deleting_restores_it(chat: ChatHarness) -> None:
    opp, contact = setup_job(chat)
    made = chat.client.post(
        f"{M}/templates",
        json={"name": "Follow-up 1", "channel": "email", "base_key": "follow_up_1",
              "subject": "Checking in, {{my_name}}",
              "body": "Hi {{recipient_first}}, news on {{role}}?"},
    )  # fmt: skip
    assert made.status_code == 201
    listed = next(
        t
        for t in made.json() and chat.client.get(f"{M}/templates").json()
        if t["key"] == "sys:follow_up_1"
    )
    email = next(v for v in listed["variants"] if v["channel"] == "email")
    assert email["edited"] is True and email["template_id"]
    other = next(v for v in listed["variants"] if v["channel"] == "linkedin")
    assert other["edited"] is False

    drafted = preview(chat, opp, "sys:follow_up_1", contact_id=contact).json()
    assert drafted["edited"] is True and drafted["body"] == "Hi Riya, news on Backend Engineer?"
    dup = chat.client.post(
        f"{M}/templates",
        json={
            "name": "x",
            "channel": "email",
            "base_key": "follow_up_1",
            "subject": "s",
            "body": "b",
        },
    )
    assert dup.json()["code"] == "already_edited"

    assert chat.client.delete(f"{M}/templates/{email['template_id']}").status_code == 204
    again = preview(chat, opp, "sys:follow_up_1", contact_id=contact).json()
    assert again["edited"] is False and "following up" in again["subject"].lower()


def test_templates_belong_to_their_owner(chat: ChatHarness, db: Session) -> None:
    mine = chat.client.post(
        f"{M}/templates", json={"name": "Mine", "channel": "linkedin", "body": "Hi"}
    ).json()
    tid = int(mine["key"].split(":")[1])
    other = User(email="other@example.com", full_name="Other", status="active")
    db.add(other)
    db.flush()
    db.info["user"] = other
    assert chat.client.patch(f"{M}/templates/{tid}", json={"name": "Stolen"}).status_code == 404
    assert chat.client.delete(f"{M}/templates/{tid}").status_code == 404
    assert all(t["source"] == "system" for t in chat.client.get(f"{M}/templates").json())


# ---- drafts -----------------------------------------------------------------------------------


def test_a_draft_is_filled_from_the_opportunity_contact_and_sender(chat: ChatHarness) -> None:
    opp, contact = setup_job(chat)
    chat.client.put(
        f"{M}/profile",
        json={
            "from_email": "me@work.example",
            "headline": "a backend engineer",
            "proof_points": ["Cut latency 40%."],
        },
    )
    d = preview(chat, opp, "sys:follow_up_1", contact_id=contact).json()
    assert d["to"] == "riya@zepto.example" and d["to_name"] == "Riya Sharma"
    assert d["from_email"] == "me@work.example"
    assert d["subject"].startswith("Following up: Backend Engineer application")
    assert "Hi Riya," in d["body"] and "Zepto" in d["body"] and "Cut latency 40%." in d["body"]
    assert "me@work.example" in d["body"] and d["missing"] == [] and d["warnings"] == []
    assert d["tips"] and d["char_limit"] is None


def test_gaps_are_listed_and_can_be_filled(chat: ChatHarness) -> None:
    opp, contact = setup_job(chat, stage="screening")
    d = preview(chat, opp, "sys:thank_you_screening", contact_id=contact).json()
    assert [m["name"] for m in d["missing"]] == ["talking_point"]
    assert "[[something specific you discussed]]" in d["body"]
    assert any("Fill in" in w for w in d["warnings"])
    filled = preview(chat, opp, "sys:thank_you_screening", contact_id=contact,
                     fields={"talking_point": "the payments roadmap"}).json()  # fmt: skip
    assert "the payments roadmap" in filled["body"] and filled["missing"] == []


def test_a_draft_without_a_contact_says_so_and_uses_a_neutral_greeting(chat: ChatHarness) -> None:
    opp, _ = setup_job(chat)
    d = preview(chat, opp, "sys:follow_up_1").json()
    assert d["to"] is None and "Hi there," in d["body"]
    assert any("Choose who" in w for w in d["warnings"])


def test_channel_specific_warnings_and_limits(chat: ChatHarness) -> None:
    opp, _ = setup_job(chat, stage="found")
    bare = chat.client.post(
        "/api/v1/contacts", json={"opportunity_id": opp, "name": "Sam", "role": "recruiter"}
    ).json()
    email = preview(chat, opp, "sys:recruiter_intro", contact_id=bare["id"]).json()
    assert any("no email" in w for w in email["warnings"])
    li = preview(chat, opp, "sys:recruiter_intro", "linkedin", contact_id=bare["id"]).json()
    assert any("no LinkedIn link" in w for w in li["warnings"]) and li["subject"] is None
    note = preview(chat, opp, "sys:connect_note", "linkedin_note", contact_id=bare["id"]).json()
    assert note["char_limit"] == 300 and note["char_count"] <= 300


def test_unknown_templates_channels_and_other_users_data_are_refused(
    chat: ChatHarness, db: Session
) -> None:
    opp, contact = setup_job(chat)
    assert preview(chat, opp, "sys:nope").json()["code"] == "no_such_template"
    assert preview(chat, opp, "sys:share_details", "linkedin").status_code == 404  # email-only
    assert preview(chat, opp, "usr:999999").status_code == 404
    assert preview(chat, opp, "garbage").status_code == 404
    assert preview(chat, opp, "sys:follow_up_1", contact_id=999999).status_code == 404
    assert (
        chat.client.post(
            f"{O}/{opp}/messages/preview",
            json={"template_key": "sys:follow_up_1", "channel": "sms"},
        ).status_code
        == 422
    )
    other = User(email="other@example.com", full_name="Other", status="active")
    db.add(other)
    db.flush()
    db.info["user"] = other
    assert preview(chat, opp, "sys:follow_up_1").status_code == 404
    assert chat.client.get(f"{O}/{opp}/messages/suggestions").status_code == 404
    assert sent(chat, opp, "sys:follow_up_1").status_code == 404
    assert contact


def test_the_attachment_hint_names_the_resume_to_send(chat: ChatHarness) -> None:
    opp, contact = setup_job(chat)
    assert preview(chat, opp, "sys:follow_up_1", contact_id=contact).json()["attach"] is None
    rid = create_resume(chat, "Backend v3")
    script_profile(chat)
    assert upload(chat, rid, make_pdf([RESUME_TEXT])).status_code == 201
    hint = preview(chat, opp, "sys:follow_up_1", contact_id=contact).json()["attach"]
    assert hint["label"] == "Backend v3" and hint["has_file"] is True
    assert (
        preview(chat, opp, "sys:follow_up_1", "linkedin", contact_id=contact).json()["attach"]
        is None
    )


# ---- sending, replying, cadence ---------------------------------------------------------------


def test_marking_sent_logs_the_contact_closes_the_reminder_and_plans_the_next(
    chat: ChatHarness,
) -> None:
    opp, contact = setup_job(chat)  # moving to "applied" created one pending follow-up
    pending = chat.client.get(
        "/api/v1/followups", params={"opportunity_id": opp, "status": "pending"}
    ).json()
    assert len(pending) == 1

    res = sent(
        chat,
        opp,
        "sys:applied_intro",
        contact_id=contact,
        subject="Applied: Backend Engineer",
        body="Hi Riya",
    ).json()
    assert (
        res["followup_closed_id"] == pending[0]["id"]
        and res["next_followup_id"]
        and res["next_followup_due"]
    )
    assert (
        res["message"]["template_key"] == "sys:applied_intro" and res["already_recorded"] is False
    )

    interactions = chat.client.get("/api/v1/interactions", params={"opportunity_id": opp}).json()
    mail = [i for i in interactions if i["type"] == "email"]
    assert len(mail) == 1 and mail[0]["direction"] == "out" and mail[0]["contact_id"] == contact
    assert chat.client.get(f"{O}/{opp}").json()["days_since_contact"] == 0
    now_pending = chat.client.get(
        "/api/v1/followups", params={"opportunity_id": opp, "status": "pending"}
    ).json()
    assert [f["id"] for f in now_pending] == [res["next_followup_id"]]


def test_the_final_nudge_and_custom_templates_schedule_nothing(chat: ChatHarness) -> None:
    opp, _ = setup_job(chat)
    assert sent(chat, opp, "sys:follow_up_final").json()["next_followup_id"] is None
    mine = chat.client.post(
        f"{M}/templates", json={"name": "Mine", "channel": "email", "subject": "s", "body": "b"}
    ).json()
    assert sent(chat, opp, mine["key"]).json()["next_followup_id"] is None
    assert (
        sent(chat, opp, "sys:follow_up_1", schedule_next=False).json()["next_followup_id"] is None
    )


def test_a_retried_send_is_recorded_once(chat: ChatHarness) -> None:
    opp, contact = setup_job(chat)
    rid = str(uuid.uuid4())
    first = sent(chat, opp, "sys:follow_up_1", contact_id=contact, request_id=rid).json()
    again = sent(chat, opp, "sys:follow_up_1", contact_id=contact, request_id=rid).json()
    assert again["already_recorded"] is True and again["message"]["id"] == first["message"]["id"]
    assert len(chat.client.get(f"{O}/{opp}/messages").json()) == 1
    mail = [
        i
        for i in chat.client.get("/api/v1/interactions", params={"opportunity_id": opp}).json()
        if i["type"] == "email"
    ]
    assert len(mail) == 1


def test_send_input_is_validated(chat: ChatHarness) -> None:
    opp, _ = setup_job(chat)
    assert sent(chat, opp, "sys:follow_up_1", body="").status_code == 422
    assert sent(chat, opp, "sys:follow_up_1", body="x" * 3001).status_code == 422
    assert sent(chat, opp, "sys:follow_up_1", channel="sms").status_code == 422
    assert sent(chat, opp, "sys:follow_up_1", contact_id=999999).status_code == 404
    assert sent(chat, opp, "sys:nope").status_code == 404
    assert sent(chat, opp, "sys:follow_up_1", body="a\x00b").json()["message"]["body"] == "ab"


def test_a_reply_is_logged_and_ends_the_auto_reminders(chat: ChatHarness) -> None:
    opp, contact = setup_job(chat)
    mid = sent(chat, opp, "sys:applied_intro", contact_id=contact).json()["message"]["id"]
    manual = chat.client.post(
        "/api/v1/followups",
        json={"opportunity_id": opp, "due_date": "2030-01-01", "message_draft": "mine"},
    ).json()
    replied = chat.client.post(f"{M}/{mid}/replied").json()
    assert replied["replied_at"]
    inbound = [
        i
        for i in chat.client.get("/api/v1/interactions", params={"opportunity_id": opp}).json()
        if i["direction"] == "in"
    ]
    assert len(inbound) == 1
    pending = chat.client.get(
        "/api/v1/followups", params={"opportunity_id": opp, "status": "pending"}
    ).json()
    assert [f["id"] for f in pending] == [manual["id"]]  # the auto one is skipped, the user's stays
    assert chat.client.post(f"{M}/{mid}/replied").status_code == 200  # twice is harmless
    assert (
        len(
            [
                i
                for i in chat.client.get(
                    "/api/v1/interactions", params={"opportunity_id": opp}
                ).json()
                if i["direction"] == "in"
            ]
        )
        == 1
    )
    assert chat.client.post(f"{M}/999999/replied").status_code == 404


def test_suggestions_follow_the_stage_and_respect_the_cooldown(chat: ChatHarness) -> None:
    opp, contact = setup_job(chat, stage="found")
    s = chat.client.get(f"{O}/{opp}/messages/suggestions").json()
    assert (
        s["suggestions"][0]["template_key"] == "sys:recruiter_intro" and s["suggestions"][0]["due"]
    )
    assert s["contacts"][0]["id"] == contact and s["contacts"][0]["last_messaged_days"] is None
    sent(chat, opp, "sys:recruiter_intro", contact_id=contact)
    s = chat.client.get(f"{O}/{opp}/messages/suggestions").json()
    assert s["contacts"][0]["last_messaged_days"] == 0
    assert all(x["template_key"] != "sys:recruiter_intro" for x in s["suggestions"])
    empty, _ = (int(chat.client.post(O, json={"company": "NoOne", "role": "R"}).json()["id"]), 0)
    assert (
        chat.client.get(f"{O}/{empty}/messages/suggestions").json()["suggestions"][0]["kind"]
        == "add_contact"
    )


def test_stats_count_sent_and_replied_by_template(chat: ChatHarness) -> None:
    opp, contact = setup_job(chat)
    a = sent(chat, opp, "sys:follow_up_1", contact_id=contact).json()["message"]["id"]
    sent(chat, opp, "sys:follow_up_1", contact_id=contact)
    sent(chat, opp, "sys:applied_intro", channel="linkedin", contact_id=contact)
    chat.client.post(f"{M}/{a}/replied")
    stats = chat.client.get(f"{M}/stats").json()
    assert stats["sent"] == 3 and stats["replied"] == 1 and round(stats["reply_rate"], 2) == 0.33
    top = stats["by_template"][0]
    assert (
        top["key"] == "sys:follow_up_1"
        and top["sent"] == 2
        and top["replied"] == 1
        and top["reply_rate"] == 0.5
    )
    assert top["name"] == "Follow-up 1: checking in"
    assert chat.client.get(f"{O}/{opp}/messages").json()[0]["template_name"]


# ---- AI polish --------------------------------------------------------------------------------

DRAFT = (
    "Hi Riya,\n\nI applied for the Backend Engineer role at Zepto and wanted to check in on my "
    "application. Thank you for your time.\n\nBalaji"
)


def script_polish(chat: ChatHarness, body: str, subject: str | None = None) -> None:
    chat.google.script(
        FakeStep(message=AIMessage(content="{}"), parsed=Polished(subject=subject, body=body))
    )


def polish(
    chat: ChatHarness, opp: int, body: str = DRAFT, instruction: str = "shorter", **kw: Any
) -> Any:
    return chat.client.post(
        f"{O}/{opp}/messages/polish", json={"body": body, "instruction": instruction, **kw}
    )


def test_polish_returns_a_faithful_rewrite(chat: ChatHarness) -> None:
    opp, _ = setup_job(chat)
    script_polish(
        chat,
        "Hi Riya,\n\nI applied for the Backend Engineer role at Zepto and wanted to "
        "check in.\n\nBalaji",
        "Quick follow-up",
    )
    res = polish(chat, opp, subject="Following up: Backend Engineer").json()
    assert res["changed"] is True and res["notice"] is None and res["subject"] == "Quick follow-up"
    [call] = [c for c in chat.google.calls if c.schema is Polished]
    sent_text = " ".join(str(m.content) for m in call.messages)
    assert "<untrusted_content>" in sent_text and "Hi Riya" in sent_text


def test_polish_that_invents_facts_is_refused_and_the_original_kept(chat: ChatHarness) -> None:
    opp, _ = setup_job(chat)
    script_polish(chat, DRAFT.replace("check in", "check in. I led a team of 40 at Google"))
    res = polish(chat, opp, instruction="warmer").json()
    assert res["changed"] is False and res["body"] == DRAFT and "number" in res["notice"]


def test_polish_respects_the_opt_out_the_quota_and_input_limits(chat: ChatHarness) -> None:
    opp, _ = setup_job(chat)
    chat.settings.message_polish_daily_limit = 1
    script_polish(chat, "Hi Riya, I applied for the Backend Engineer role at Zepto. Thanks, Balaji")
    assert polish(chat, opp).status_code == 200
    blocked = polish(chat, opp)
    assert blocked.status_code == 429 and blocked.json()["code"] == "polish_quota"
    assert int(blocked.headers["retry-after"]) > 0
    assert polish(chat, opp, instruction="rude").status_code == 422
    assert polish(chat, opp, body="").status_code == 422
    chat.client.put("/api/v1/chat/preferences", json={"assistant_opt_out": True})
    off = polish(chat, opp)
    assert off.status_code == 403 and off.json()["code"] == "assistant_opted_out"


def test_polish_counts_in_the_visible_allowances(chat: ChatHarness) -> None:
    rows = {r["name"]: r for r in chat.client.get("/api/v1/chat/usage").json()}
    assert rows["polish"]["limit"] == chat.settings.message_polish_daily_limit
    assert select  # imported for clarity in other tests


# ---- the assistant ----------------------------------------------------------------------------


def test_the_assistant_drafts_the_next_message_as_a_card_and_cannot_send(chat: ChatHarness) -> None:
    from tests.assistant.test_chat_api import new_conversation, send, text_of, tool_call, verdict

    opp, _ = setup_job(chat, stage="found")
    convo = new_conversation(chat)
    chat.groq.script(
        verdict("contacts"),
        tool_call("draft_message", {"opportunity_id": opp}),
        AIMessage(content="Here is a draft to the recruiter."),
    )
    events = send(chat, convo, "Draft a message to the Zepto recruiter")

    [cards] = [d for n, d in events if n == "cards"]
    [card] = cards["items"]
    assert card["type"] == "draft" and card["opportunity_id"] == opp
    assert card["template_key"] == "sys:recruiter_intro" and card["to_name"] == "Riya Sharma"
    assert "Zepto" in card["body"] and "Hi Riya," in card["body"]
    assert "draft" in text_of(events).lower() and "error" not in [n for n, _ in events]
    # nothing was recorded as sent: only the user can say that
    assert chat.client.get(f"{O}/{opp}/messages").json() == []


def test_the_next_reminder_is_planned_even_when_the_session_does_not_autoflush(
    chat: ChatHarness, db: Session
) -> None:
    """Production sessions don't autoflush (app/db/session.py); the tests' default does. Closing
    the old reminder must be visible to the check for a pending one either way."""
    opp, contact = setup_job(chat)
    db.autoflush = False
    res = sent(chat, opp, "sys:applied_intro", contact_id=contact).json()
    assert res["followup_closed_id"] and res["next_followup_id"] and res["next_followup_due"]
    pending = chat.client.get(
        "/api/v1/followups", params={"opportunity_id": opp, "status": "pending"}
    ).json()
    assert [f["id"] for f in pending] == [res["next_followup_id"]]


def test_polish_says_so_when_the_model_changes_nothing(chat: ChatHarness) -> None:
    opp, _ = setup_job(chat)
    script_polish(chat, DRAFT)
    res = polish(chat, opp, instruction="warmer").json()
    assert (
        res["changed"] is False and res["body"] == DRAFT and "already reads well" in res["notice"]
    )
