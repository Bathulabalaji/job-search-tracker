from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import RateLimitedError
from app.services.rate_limit import RateLimiter
from tests.conftest import NOW

WINDOW = timedelta(minutes=15)


def _limiter(db: Session, offset: timedelta = timedelta(0)) -> RateLimiter:
    return RateLimiter(db, Clock(ZoneInfo("UTC"), lambda: NOW + offset))


def test_allows_up_to_the_limit_then_blocks(db: Session) -> None:
    limiter = _limiter(db)
    for _ in range(3):
        limiter.consume("b", 3, WINDOW)
    with pytest.raises(RateLimitedError) as info:
        limiter.consume("b", 3, WINDOW)
    assert 0 < info.value.retry_after_seconds <= 900
    assert info.value.status_code == 429


def test_check_alone_does_not_count(db: Session) -> None:
    limiter = _limiter(db)
    for _ in range(10):
        limiter.check("b", 3, WINDOW)  # never raises: nothing was recorded


def test_buckets_are_independent(db: Session) -> None:
    limiter = _limiter(db)
    limiter.consume("a", 1, WINDOW)
    limiter.consume("b", 1, WINDOW)
    with pytest.raises(RateLimitedError):
        limiter.consume("a", 1, WINDOW)


def test_the_window_slides(db: Session) -> None:
    _limiter(db).consume("b", 1, WINDOW)
    with pytest.raises(RateLimitedError):
        _limiter(db, timedelta(minutes=14)).consume("b", 1, WINDOW)
    _limiter(db, timedelta(minutes=15, seconds=1)).consume("b", 1, WINDOW)


def test_retry_after_counts_down_to_the_oldest_attempt_expiring(db: Session) -> None:
    _limiter(db).consume("b", 1, WINDOW)
    with pytest.raises(RateLimitedError) as info:
        _limiter(db, timedelta(minutes=10)).consume("b", 1, WINDOW)
    assert 290 <= info.value.retry_after_seconds <= 300


def test_reset_clears_a_bucket(db: Session) -> None:
    limiter = _limiter(db)
    limiter.consume("b", 1, WINDOW)
    limiter.reset("b")
    limiter.consume("b", 1, WINDOW)
