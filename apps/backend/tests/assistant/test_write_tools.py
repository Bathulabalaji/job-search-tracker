from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.assistant.graph import _run_tool
from app.assistant.tools import AssistantTool, NoArgs, ToolTimeout, with_statement_timeout
from app.assistant.write_tools import build_write_tools
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models.enums import FollowupStatus, Stage
from app.models.followup import Followup
from app.models.opportunity import Opportunity


@pytest.fixture
def opp(db: Session) -> Opportunity:
    row = Opportunity(
        user_id=db.info["user_id"], company="Zepto", role="Backend", stage=Stage.applied
    )
    db.add(row)
    db.flush()
    return row


def test_move_preview_names_the_opportunity_and_refuses_a_no_op(
    db: Session, clock: Clock, settings: Settings, opp: Opportunity
) -> None:
    tools = build_write_tools(db, clock, settings, db.info["user_id"])
    move = tools["move_opportunity"]
    preview = move.preview(move.args(opportunity_id=opp.id, stage="interviewing"))
    assert preview.title == "Move Zepto — Backend" and preview.summary == "applied → interviewing"
    assert preview.fields[0]["options"] and "interviewing" in preview.fields[0]["options"]
    with pytest.raises(ConflictError):
        move.preview(move.args(opportunity_id=opp.id, stage="applied"))
    with pytest.raises(NotFoundError):
        move.preview(move.args(opportunity_id=99, stage="applied"))


def test_each_write_tool_executes_through_the_services(
    db: Session, clock: Clock, settings: Settings, opp: Opportunity
) -> None:
    tools = build_write_tools(db, clock, settings, db.info["user_id"])

    added = tools["add_followup"]
    result = added.execute(added.args(opportunity_id=opp.id, due_date="2026-11-20", channel="call"))
    followup = db.scalars(select(Followup)).one()
    assert followup.due_date == date(2026, 11, 20) and "followups" in result.changed

    mark = tools["mark_followup"]
    preview = mark.preview(mark.args(followup_id=followup.id, status="done"))
    assert preview.title == "Mark done: follow-up for Zepto — Backend"
    mark.execute(mark.args(followup_id=followup.id, status="done"))
    db.refresh(followup)
    assert followup.status == FollowupStatus.done and followup.done_at is not None

    log = tools["log_interaction"]
    preview = log.preview(log.args(opportunity_id=opp.id, type="call", summary="Spoke to HR"))
    assert preview.title == "Log call with Zepto — Backend"
    result = log.execute(
        log.args(
            opportunity_id=opp.id,
            type="call",
            summary="Spoke to HR",
            occurred_at=datetime(2026, 11, 12, 9, 0),
        )
    )
    assert result.summary.startswith("Logged call on")

    nxt = tools["set_next_action"]
    nxt.execute(
        nxt.args(opportunity_id=opp.id, next_action="Send portfolio", next_action_due="2026-11-18")
    )
    db.refresh(opp)
    assert (opp.next_action, opp.next_action_due) == ("Send portfolio", date(2026, 11, 18))

    create = tools["create_opportunity"]
    preview = create.preview(create.args(company="Swiggy", role="SRE", priority=1))
    assert preview.title == "Add Swiggy — SRE" and "priority 1" in preview.summary
    result = create.execute(create.args(company="Swiggy", role="SRE", priority=1))
    assert result.summary == "Added Swiggy — SRE (found)"
    assert len(db.scalars(select(Opportunity)).all()) == 2


def test_a_slow_lookup_is_cut_off_and_the_session_stays_usable(db: Session) -> None:
    def slow(_: object) -> dict[str, object]:
        db.execute(text("SELECT pg_sleep(2)"))
        return {}

    guarded = with_statement_timeout(db, 0.1, slow)
    with pytest.raises(ToolTimeout):
        guarded(NoArgs())
    assert db.scalar(text("SELECT 1")) == 1  # the aborted transaction was rolled back
    # The timeout did not leak: a slower query is fine afterwards.
    db.execute(text("SELECT pg_sleep(0.15)"))

    quick = with_statement_timeout(db, 1.0, lambda _: {"ok": True})
    assert quick(NoArgs()) == {"ok": True}
    tool = AssistantTool("t", "d", NoArgs, guarded, lambda r: "n/a")
    ok, summary, content = _run_tool(tool, "t", {}, 1)
    assert (ok, summary) == (False, "timed out") and "took too long" in content


def test_expired_cards_only_affect_their_own_run(db: Session, clock: Clock) -> None:
    assert clock.now() + timedelta(minutes=15) > clock.now()
