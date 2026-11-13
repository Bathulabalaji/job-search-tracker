from datetime import timedelta

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import Session

from app.assistant.context import ContextBuilder
from app.assistant.graph import _run_tool
from app.assistant.tools import build_read_tools, compact
from app.core.clock import Clock
from app.core.config import Settings
from app.llm.errors import RateLimited
from app.llm.providers.fake import FakeProvider
from app.models.chat import ChatConversation, ChatMessage
from app.models.enums import Stage
from app.models.opportunity import Opportunity
from app.repositories.chat import MessageRepository
from tests.llm.helpers import MovableClock, build_gateway


def conversation_with(db: Session, turns: int, words: int = 120) -> ChatConversation:
    conversation = ChatConversation(user_id=db.info["user_id"], title="t")
    db.add(conversation)
    db.flush()
    for i in range(turns):
        for role in ("user", "assistant"):
            db.add(
                ChatMessage(
                    user_id=db.info["user_id"],
                    conversation_id=conversation.id,
                    seq=len(conversation.title) + i * 2 + (role == "assistant"),
                    role=role,
                    content=f"{role} turn {i} " + "word " * words,
                )
            )
    db.flush()
    return conversation


def test_short_history_goes_in_verbatim(db: Session) -> None:
    conversation = conversation_with(db, turns=2, words=5)
    gateway = build_gateway(db, MovableClock(), groq=FakeProvider("groq"))
    context = ContextBuilder(MessageRepository(db, db.info["user_id"]), gateway).build(
        conversation, before_seq=999
    )
    assert context.summary is None
    assert [type(m) for m in context.history] == [HumanMessage, AIMessage, HumanMessage, AIMessage]


def test_long_history_is_folded_into_a_summary_keeping_recent_turns(db: Session) -> None:
    conversation = conversation_with(db, turns=8)
    groq = FakeProvider("groq", [AIMessage(content="Goals: find backend roles")])
    gateway = build_gateway(db, MovableClock(), groq=groq)
    context = ContextBuilder(MessageRepository(db, db.info["user_id"]), gateway).build(
        conversation, before_seq=999
    )
    assert context.summary == "Goals: find backend roles"
    assert conversation.summary == context.summary and conversation.summary_through_seq
    assert isinstance(context.history[0], HumanMessage)  # never starts on a reply
    assert 4 <= len(context.history) < 16
    assert groq.calls[0].model == "openai/gpt-oss-20b"


def test_without_a_summarizer_the_fallback_is_extractive(db: Session) -> None:
    conversation = conversation_with(db, turns=8)
    groq = FakeProvider("groq", [RateLimited("x", kind="day")] * 2)
    google = FakeProvider("google", [RateLimited("x", kind="day")] * 2)
    gateway = build_gateway(db, MovableClock(), groq=groq, google=google)
    context = ContextBuilder(MessageRepository(db, db.info["user_id"]), gateway).build(
        conversation, before_seq=999
    )
    assert context.summary is not None and context.summary.startswith("Asked: user turn 0")


def test_quiet_filter_and_open_only(db: Session, clock: Clock, settings: Settings) -> None:
    uid = db.info["user_id"]
    old = clock.now() - timedelta(days=20)
    db.add_all(
        [
            Opportunity(
                user_id=uid, company="Quiet", role="BE", stage=Stage.applied, created_at=old
            ),
            Opportunity(user_id=uid, company="Fresh", role="BE", stage=Stage.applied),
            Opportunity(
                user_id=uid, company="Closed", role="BE", stage=Stage.rejected, created_at=old
            ),
        ]
    )
    db.flush()
    tools = build_read_tools(db, clock, settings, uid)
    tool = tools["list_opportunities"]
    result = tool.run(tool.args(quiet_for_days=14, open_only=True))
    assert [i["company"] for i in result["items"]] == ["Quiet"]


def test_run_tool_reports_bad_arguments_and_caps_calls(
    db: Session, clock: Clock, settings: Settings
) -> None:
    tools = build_read_tools(db, clock, settings, db.info["user_id"])
    ok, summary, content = _run_tool(
        tools["get_opportunity"], "get_opportunity", {"opportunity_id": "x"}, 1
    )
    assert (ok, summary) == (False, "invalid arguments") and "Invalid arguments" in content
    ok, summary, _ = _run_tool(tools["get_today"], "get_today", {}, 7)
    assert (ok, summary) == (False, "tool limit reached")
    ok, summary, _ = _run_tool(None, "drop_tables", {}, 1)
    assert (ok, summary) == (False, "unknown tool")


def test_compact_truncates_long_results() -> None:
    text = compact({"items": ["x" * 100] * 50})
    assert len(text) <= 1400 and text.endswith('ask for fewer rows)"')
