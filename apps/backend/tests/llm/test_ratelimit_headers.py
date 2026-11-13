import pytest

from app.llm.ratelimit_headers import RateLimitHeaders, parse_duration, parse_retry_after


@pytest.mark.parametrize(
    ("raw", "seconds"),
    [
        ("1m2.5s", 62.5),
        ("7.66s", 7.66),
        ("250ms", 0.25),
        ("1h2m3s", 3723.0),
        ("3", 3.0),
        (" 2m ", 120.0),
        ("", None),
        (None, None),
        ("soon", None),
        ("1m2x", None),
    ],
)
def test_parse_duration(raw: str | None, seconds: float | None) -> None:
    assert parse_duration(raw) == seconds


def test_retry_after_is_whole_seconds_and_at_least_one() -> None:
    assert parse_retry_after("0.2") == 1
    assert parse_retry_after("42") == 42
    assert parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is None


def test_groq_headers_are_read_case_insensitively() -> None:
    parsed = RateLimitHeaders.from_mapping(
        {
            "X-RateLimit-Remaining-Requests": "998",
            "x-ratelimit-remaining-tokens": "4500",
            "x-ratelimit-reset-requests": "2m59.56s",
            "x-ratelimit-reset-tokens": "7.66s",
            "Retry-After": "8",
        }
    )
    assert parsed.remaining_requests == 998
    assert parsed.remaining_tokens == 4500
    assert parsed.requests_reset_in == pytest.approx(179.56)
    assert parsed.tokens_reset_in == pytest.approx(7.66)
    assert parsed.retry_after == 8
    assert not parsed.empty


def test_missing_headers_are_empty() -> None:
    assert RateLimitHeaders.from_mapping(None).empty
    assert RateLimitHeaders.from_mapping({"content-type": "application/json"}).empty
