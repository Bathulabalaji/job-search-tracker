"""Operator tool for the AI gateway: `uv run python -m app.scripts.llm_admin <command> ...`

ping [--task chat.agent] [TEXT]   one message through the router: model, latency, tokens
status                            per-model budget, cooldowns and circuit state
reset-cooldowns                   clear cooldowns and circuits (after fixing a key, say)
usage [--since 7d]                calls, tokens and errors per provider, model and task
"""

import argparse
import json
import re
from datetime import timedelta
from time import perf_counter
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.llm import build_llm_gateway
from app.llm.errors import LLMError
from app.llm.gateway import LLMGateway
from app.llm.policy import Task

_SINCE = re.compile(r"^(\d+)([mhd])$")


def _since(text: str) -> timedelta:
    match = _SINCE.match(text.strip().lower())
    if match is None:
        raise SystemExit("--since must look like 30m, 24h or 7d")
    amount, unit = int(match.group(1)), match.group(2)
    return timedelta(**{{"m": "minutes", "h": "hours", "d": "days"}[unit]: amount})


def _gateway(session: Session, settings: Settings) -> LLMGateway:
    clock = Clock(tz=ZoneInfo(settings.timezone))
    return build_llm_gateway(settings, session, clock)


def cmd_ping(gateway: LLMGateway, settings: Settings, args: argparse.Namespace) -> None:
    if not settings.llm_enabled:
        raise SystemExit("Set GROQ_API_KEY and/or GOOGLE_AI_API_KEY in apps/backend/.env first")
    messages = [
        SystemMessage(content="You are a terse assistant. Answer in one short sentence."),
        HumanMessage(content=args.text),
    ]
    started = perf_counter()
    try:
        result = gateway.chat(Task(args.task), messages)
    except LLMError as exc:
        raise SystemExit(f"{exc.code}: {exc.user_message}\n  detail: {exc.detail}") from exc
    latency = int((perf_counter() - started) * 1000)
    usage = result.usage
    print(f"model      {result.model} ({result.provider})")
    print(f"switches   {result.switches}")
    print(f"latency    {latency} ms")
    if usage is not None:
        kind = "estimated" if usage.estimated else "reported"
        print(f"tokens     {usage.prompt_tokens} in / {usage.completion_tokens} out ({kind})")
    print(f"reply      {result.text.strip()[:300]}")


def cmd_status(gateway: LLMGateway, settings: Settings, args: argparse.Namespace) -> None:
    rows = gateway.status()
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    print(f"{'model':40} {'provider':8} {'state':12} {'min req/tok':14} {'day req/tok':16} circuit")
    for row in rows:
        minute = row["minute"]
        day = row["day"]
        assert isinstance(minute, dict) and isinstance(day, dict)
        state = "available" if row["available"] else str(row["reason"] or "blocked")
        print(
            f"{str(row['model']):40} {str(row['provider']):8} {state:12} "
            f"{minute['requests']!s:>5}/{minute['tokens']!s:<8} "
            f"{day['requests']!s:>6}/{day['tokens']!s:<9} {row['circuit']}"
        )


def cmd_reset(gateway: LLMGateway, settings: Settings, args: argparse.Namespace) -> None:
    print(f"cleared {gateway.ledger.reset_cooldowns()} model(s)")


def cmd_usage(gateway: LLMGateway, settings: Settings, args: argparse.Namespace) -> None:
    since = gateway.clock.now() - _since(args.since)
    rows = gateway.ledger.usage(since)
    if not rows:
        print(f"no provider calls since {since.isoformat(timespec='minutes')}")
        return
    print(
        f"{'provider':8} {'model':40} {'task':20} {'outcome':12} "
        f"{'calls':>6} {'in':>8} {'out':>8} {'avg ms':>6}"
    )
    for row in rows:
        print(
            f"{row.provider:8} {row.resource:40} {row.task:20} {row.outcome:12} "
            f"{row.calls:>6} {row.prompt_tokens:>8} {row.completion_tokens:>8} "
            f"{row.avg_latency_ms:>6}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ping = sub.add_parser("ping")
    ping.add_argument("text", nargs="?", default="Say hello in five words.")
    ping.add_argument("--task", default=Task.chat_agent.value, choices=[t.value for t in Task])
    ping.set_defaults(func=cmd_ping)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)
    sub.add_parser("reset-cooldowns").set_defaults(func=cmd_reset)
    usage = sub.add_parser("usage")
    usage.add_argument("--since", default="7d")
    usage.set_defaults(func=cmd_usage)
    args = parser.parse_args()
    settings = get_settings()
    with SessionLocal() as session:
        args.func(_gateway(session, settings), settings, args)


if __name__ == "__main__":
    main()
