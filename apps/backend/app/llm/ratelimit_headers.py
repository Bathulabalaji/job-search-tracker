"""Rate-limit headers in the OpenAI style that Groq sends on every response.

Google sends none; its 429 body carries a RetryInfo instead, which the adapter maps to
`retry_after`. Everything here is tolerant: a header we cannot parse is simply absent.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def parse_duration(value: str | None) -> float | None:
    """'1m2.5s' -> 62.5, '7.66s' -> 7.66, '250ms' -> 0.25, '3' -> 3.0; None when unparseable."""
    if value is None:
        return None
    text = value.strip().lower().replace(" ", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    total = 0.0
    consumed = 0
    for number, unit in _PART.findall(text):
        consumed += len(number) + len(unit)
        amount = float(number)
        if unit == "h":
            total += amount * 3600
        elif unit == "m":
            total += amount * 60
        elif unit == "ms":
            total += amount / 1000
        else:
            total += amount
    return total if consumed == len(text) else None


def parse_retry_after(value: str | None) -> int | None:
    """Seconds from a Retry-After header. HTTP-date forms are ignored (never seen from Groq)."""
    if value is None:
        return None
    try:
        return max(1, int(float(value.strip())))
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value.strip()))
    except ValueError:
        return None


@dataclass(frozen=True)
class RateLimitHeaders:
    remaining_requests: int | None = None
    remaining_tokens: int | None = None
    requests_reset_in: float | None = None  # seconds
    tokens_reset_in: float | None = None  # seconds
    retry_after: int | None = None  # seconds, only on 429

    @classmethod
    def from_mapping(cls, headers: Mapping[str, str] | None) -> "RateLimitHeaders":
        if not headers:
            return cls()
        lower = {key.lower(): value for key, value in headers.items()}
        return cls(
            remaining_requests=_int(lower.get("x-ratelimit-remaining-requests")),
            remaining_tokens=_int(lower.get("x-ratelimit-remaining-tokens")),
            requests_reset_in=parse_duration(lower.get("x-ratelimit-reset-requests")),
            tokens_reset_in=parse_duration(lower.get("x-ratelimit-reset-tokens")),
            retry_after=parse_retry_after(lower.get("retry-after")),
        )

    @property
    def empty(self) -> bool:
        return self == RateLimitHeaders()
