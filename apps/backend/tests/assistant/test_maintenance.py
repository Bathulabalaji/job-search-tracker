"""Phase 5: the scheduled sweep expires, archives and deletes what has aged out."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat import ChatConversation, ChatMessage, ChatRun
from app.models.chat_action import ChatPendingAction
from app.models.job_posting import JobPosting
from app.models.opportunity import Opportunity
from app.models.provider_ledger import ProviderUsageEvent
from tests.assistant.conftest import ChatHarness

URL = "/api/v1/internal/maintenance"
SECRET = {"X-Maintenance-Secret": "s3cret-value"}


def enable(chat: ChatHarness) -> None:
    chat.settings.maintenance_secret = "s3cret-value"


def conversation(
    db: Session, now: datetime, *, idle_days: int, status: str = "active", run: str | None = None
) -> tuple[ChatConversation, ChatRun | None]:
    when = now - timedelta(days=idle_days)
    convo = ChatConversation(
        user_id=db.info["user_id"], title="t", status=status, last_message_at=when
    )
    db.add(convo)
    db.flush()
    message = ChatMessage(
        user_id=db.info["user_id"],
        conversation_id=convo.id,
        seq=1,
        role="user",
        content="hi",
        created_at=when,
    )
    db.add(message)
    db.flush()
    chat_run = None
    if run is not None:
        chat_run = ChatRun(
            id=uuid.uuid4(),
            user_id=db.info["user_id"],
            conversation_id=convo.id,
            user_message_id=message.id,
            status=run,
            started_at=when,
            finished_at=None if run in ("running", "awaiting_confirmation") else when,
        )
        db.add(chat_run)
        db.flush()
    return convo, chat_run


def test_the_endpoint_is_hidden_until_configured_and_needs_the_secret(chat: ChatHarness) -> None:
    assert chat.client.post(URL, headers=SECRET).status_code == 404  # not configured
    enable(chat)
    assert chat.client.post(URL).status_code == 403
    wrong = chat.client.post(URL, headers={"X-Maintenance-Secret": "nope"})
    assert wrong.status_code == 403 and wrong.json()["code"] == "bad_maintenance_secret"
    ok = chat.client.post(URL, headers=SECRET)
    assert ok.status_code == 200 and set(ok.json()) >= {"checkpoints_pruned", "actions_expired"}


def test_conversations_age_from_active_to_archived_to_gone(chat: ChatHarness, db: Session) -> None:
    enable(chat)
    now = chat.clock.now
    fresh, _ = conversation(db, now, idle_days=5)
    stale, _ = conversation(db, now, idle_days=100)
    old, old_run = conversation(db, now, idle_days=200, status="archived", run="completed")
    recent_archived, _ = conversation(db, now, idle_days=120, status="archived")
    assert old_run is not None
    fresh_id, stale_id, old_id, recent_id = fresh.id, stale.id, old.id, recent_archived.id

    first = chat.client.post(URL, headers=SECRET).json()

    assert first["conversations_archived"] == 1 and first["conversations_purged"] == 1
    db.expire_all()
    status = {c.id: c.status for c in db.scalars(select(ChatConversation))}
    assert status[fresh_id] == "active" and status[stale_id] == "archived"
    assert old_id not in status and status[recent_id] == "archived"
    assert db.scalar(select(func.count()).select_from(ChatMessage)) == 3  # the purged one cascaded

    second = chat.client.post(URL, headers=SECRET).json()
    assert second["conversations_archived"] == 0 and second["conversations_purged"] == 0


def test_overdue_confirmations_expire_and_their_runs_close(chat: ChatHarness, db: Session) -> None:
    enable(chat)
    now = chat.clock.now
    convo, run = conversation(db, now, idle_days=0, run="awaiting_confirmation")
    assert run is not None
    live, live_run = conversation(db, now, idle_days=0, run="awaiting_confirmation")
    assert live_run is not None
    for r, expires in ((run, now - timedelta(minutes=1)), (live_run, now + timedelta(minutes=10))):
        db.add(
            ChatPendingAction(
                user_id=db.info["user_id"],
                conversation_id=r.conversation_id,
                run_id=r.id,
                tool_call_id="c1",
                tool_name="move_opportunity",
                args={},
                preview={},
                status="pending",
                expires_at=expires,
                created_at=now,
            )
        )
    db.flush()
    run_id, live_run_id = run.id, live_run.id

    report = chat.client.post(URL, headers=SECRET).json()

    assert report["actions_expired"] == 1
    db.expire_all()
    closed = db.get(ChatRun, run_id)
    assert (
        closed is not None
        and closed.status == "cancelled"
        and closed.error_code == "action_expired"
    )
    waiting = db.get(ChatRun, live_run_id)
    assert waiting is not None and waiting.status == "awaiting_confirmation"
    assert convo.id != live.id


def test_old_runs_have_their_checkpoints_pruned_but_recent_ones_stay(
    chat: ChatHarness, db: Session
) -> None:
    enable(chat)
    now = chat.clock.now
    _, old_run = conversation(db, now, idle_days=3, run="completed")
    _, new_run = conversation(db, now, idle_days=0, run="failed")
    assert old_run is not None and new_run is not None
    deleted: list[str] = []
    chat.checkpointer.delete_thread = deleted.append  # type: ignore[method-assign]

    report = chat.client.post(URL, headers=SECRET).json()

    assert deleted == [str(old_run.id)] and report["checkpoints_pruned"] == 1


def test_expired_postings_and_old_usage_rows_go_but_tracked_postings_stay(
    chat: ChatHarness, db: Session
) -> None:
    enable(chat)
    now = chat.clock.now

    def posting(n: int, expires_in_days: int) -> JobPosting:
        row = JobPosting(
            provider="serpapi",
            external_id=str(n),
            canonical_url=f"https://x.example/{n}",
            fingerprint=f"{n:040d}",
            title="T",
            company="C",
            source_site="company",
            apply_url=f"https://x.example/{n}",
            fetched_at=now,
            expires_at=now + timedelta(days=expires_in_days),
        )
        db.add(row)
        db.flush()
        return row

    gone, tracked, live = posting(1, -2), posting(2, -2), posting(3, 5)
    db.add(
        Opportunity(user_id=db.info["user_id"], company="C", role="R", job_posting_id=tracked.id)
    )
    for days_ago in (200, 1):
        db.add(
            ProviderUsageEvent(
                kind="llm",
                provider="groq",
                resource="m",
                task="t",
                outcome="ok",
                created_at=now - timedelta(days=days_ago),
            )
        )
    db.flush()
    gone_id, tracked_id, live_id = gone.id, tracked.id, live.id

    report = chat.client.post(URL, headers=SECRET).json()

    assert report["job_postings_deleted"] == 1 and report["usage_events_deleted"] == 1
    db.expire_all()
    remaining = {p.id for p in db.scalars(select(JobPosting))}
    assert remaining == {tracked_id, live_id} and gone_id not in remaining
    assert db.scalar(select(func.count()).select_from(ProviderUsageEvent)) == 1
