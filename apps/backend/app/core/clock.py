from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Clock:
    """Injectable time source so services and tests agree on 'now' and 'today'."""

    tz: ZoneInfo
    now_fn: Callable[[], datetime] = field(default=_utc_now)

    def now(self) -> datetime:
        return self.now_fn()

    def today(self) -> date:
        return self.now().astimezone(self.tz).date()
