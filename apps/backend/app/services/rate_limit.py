from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import RateLimitedError
from app.repositories.user import RateLimitRepository


class RateLimiter:
    """Fixed-window attempt counters stored in PostgreSQL, so every worker shares them."""

    def __init__(self, session: Session, clock: Clock) -> None:
        self.events = RateLimitRepository(session)
        self.clock = clock

    def check(self, bucket: str, limit: int, window: timedelta) -> None:
        """Raise RateLimitedError if `bucket` already used up `limit` attempts in `window`."""
        now = self.clock.now()
        self.events.purge_older_than(bucket, now - window)
        count, oldest = self.events.window_stats(bucket, now - window)
        if count >= limit:
            retry = int(((oldest or now) + window - now).total_seconds())
            raise RateLimitedError(retry)

    def record(self, bucket: str) -> None:
        self.events.add(bucket, self.clock.now())

    def consume(self, bucket: str, limit: int, window: timedelta) -> None:
        """Count this attempt, refusing it when the limit is already reached."""
        self.check(bucket, limit, window)
        self.record(bucket)

    def reset(self, bucket: str) -> None:
        self.events.clear(bucket)
