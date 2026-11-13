"""Builders shared by the gateway tests: a gateway over fake providers, a movable clock."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.llm.catalog import Catalog, Provider, load_catalog
from app.llm.gateway import LLMGateway
from app.llm.ledger import BudgetLedger
from app.llm.policy import Policy, load_policy
from app.llm.providers.fake import FakeProvider
from tests.conftest import NOW


class MovableClock:
    def __init__(self, start: datetime = NOW) -> None:
        self.now = start
        self.clock = Clock(tz=ZoneInfo("Asia/Kolkata"), now_fn=lambda: self.now)

    def advance(self, **delta: float) -> None:
        self.now = self.now + timedelta(**delta)


def build_gateway(
    db: Session,
    movable: MovableClock,
    *,
    groq: FakeProvider | None = None,
    google: FakeProvider | None = None,
    limits: str = "",
    policy_override: str = "",
    max_switches: int = 3,
    run_timeout: float = 90.0,
    catalog: Catalog | None = None,
    policy: Policy | None = None,
) -> LLMGateway:
    catalog = catalog or load_catalog(limits)
    policy = policy or load_policy(policy_override, catalog)
    providers = {}
    if groq is not None:
        providers[Provider.groq] = groq
    if google is not None:
        providers[Provider.google] = google
    return LLMGateway(
        ledger=BudgetLedger(db, movable.clock, catalog),
        providers=providers,
        policy=policy,
        catalog=catalog,
        clock=movable.clock,
        max_switches=max_switches,
        run_timeout=run_timeout,
        sleep=lambda _: None,  # never actually wait in tests
        user_id=db.info["user_id"],
    )


def prompt(text: str = "What is due today?") -> list[SystemMessage | HumanMessage]:
    return [SystemMessage(content="You are helpful."), HumanMessage(content=text)]
