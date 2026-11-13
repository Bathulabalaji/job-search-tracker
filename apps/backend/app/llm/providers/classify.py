"""Turns provider SDK exceptions into `app.llm.errors`.

Both SDKs change their exception classes between majors, so this reads the *shape* of an
exception (status code, headers, message text, LangChain's standard model errors) rather than
importing provider classes. Unknown errors become `ProviderUnavailable`, which the gateway
retries once and then routes around.
"""

import re
from collections.abc import Mapping
from typing import Any

from langchain_core.exceptions import (
    ContextOverflowError,
    ModelAuthenticationError,
    ModelConnectionError,
    ModelInvalidRequestError,
    ModelNotFoundError,
    ModelPermissionDeniedError,
    ModelRateLimitError,
    ModelRefusalError,
    ModelTimeoutError,
)

from app.llm.errors import (
    ContentBlocked,
    ContextTooLong,
    LLMError,
    ProviderAuthFailed,
    ProviderBadRequest,
    ProviderUnavailable,
    RateLimited,
)
from app.llm.ratelimit_headers import parse_duration

_CONTEXT_PHRASES = (
    "context_length_exceeded",
    "maximum context length",
    "reduce the length of the messages",
    "exceeds the maximum number of tokens",
    "token limit",
    "input is too long",
)
_DAY_PHRASES = ("per day", "(rpd)", "(tpd)", "perday", "daily")
_BLOCKED_PHRASES = ("content_filter", "safety", "prohibited_content", "blocked", "recitation")
_HEADER_PREFIXES = ("x-ratelimit", "retry-after")


def classify_exception(exc: BaseException, *, provider: str, model: str) -> LLMError:
    if isinstance(exc, LLMError):
        return exc
    cause = exc.__cause__
    status = _status_code(exc) or (_status_code(cause) if cause else None)
    text = _text(exc, cause)
    headers = _headers(exc) or (_headers(cause) if cause else {})
    detail = f"{type(exc).__name__}: {str(exc)[:500]}"
    common: dict[str, Any] = {"provider": provider, "model": model}

    if isinstance(exc, ContextOverflowError) or _mentions(text, _CONTEXT_PHRASES):
        return ContextTooLong(detail, **common)
    if isinstance(exc, ModelRateLimitError) or status == 429:
        kind = "day" if _mentions(text, _DAY_PHRASES) else "minute"
        retry_after = _retry_after(headers, cause or exc, text)
        return RateLimited(detail, kind=kind, headers=headers, retry_after=retry_after, **common)
    if isinstance(exc, ModelAuthenticationError | ModelPermissionDeniedError) or status in (
        401,
        403,
    ):
        return ProviderAuthFailed(detail, **common)
    if isinstance(exc, ModelTimeoutError) or _is_timeout(exc, cause, text):
        return ProviderUnavailable(detail, kind="timeout", **common)
    if isinstance(exc, ModelConnectionError) or _is_connection_error(exc, cause):
        return ProviderUnavailable(detail, kind="connection", **common)
    if isinstance(exc, ModelRefusalError):
        return ContentBlocked(detail, **common)
    if isinstance(exc, ModelInvalidRequestError | ModelNotFoundError) or status in (
        400,
        404,
        422,
    ):
        if _mentions(text, _BLOCKED_PHRASES):
            return ContentBlocked(detail, **common)
        return ProviderBadRequest(detail, **common)
    return ProviderUnavailable(detail, kind="error", **common)


# ---- helpers --------------------------------------------------------------------------------


def _status_code(exc: BaseException | None) -> int | None:
    if exc is None:
        return None
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value
    return None


def _text(exc: BaseException, cause: BaseException | None) -> str:
    parts = [str(exc)]
    message = getattr(exc, "message", None)
    if isinstance(message, str):
        parts.append(message)
    if cause is not None:
        parts.append(str(cause))
        details = getattr(cause, "details", None)
        if details:
            parts.append(str(details))
    return " ".join(parts).lower()


def _headers(exc: BaseException | None) -> dict[str, str]:
    response = getattr(exc, "response", None)
    raw = getattr(response, "headers", None)
    if raw is None:
        return {}
    try:
        items = raw.items() if isinstance(raw, Mapping) or hasattr(raw, "items") else []
    except Exception:  # an odd headers object: not worth failing the classification
        return {}
    return {
        str(key): str(value)
        for key, value in items
        if str(key).lower().startswith(_HEADER_PREFIXES)
    }


def _mentions(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _is_timeout(exc: BaseException, cause: BaseException | None, text: str) -> bool:
    names = type(exc).__name__.lower() + (type(cause).__name__.lower() if cause else "")
    return "timeout" in names or "timed out" in text or isinstance(exc, TimeoutError)


def _is_connection_error(exc: BaseException, cause: BaseException | None) -> bool:
    names = type(exc).__name__.lower() + (type(cause).__name__.lower() if cause else "")
    return "connect" in names or isinstance(exc, ConnectionError | OSError)


_RETRY_IN = re.compile(r"try again in ([0-9hms.]+)")


def _retry_after(headers: Mapping[str, str], exc: BaseException, text: str) -> int | None:
    """Retry-After header (Groq), RetryInfo in the error body (Google), or 'try again in 3.2s'
    in the message (Groq), whichever is present."""
    for key, value in headers.items():
        if key.lower() == "retry-after":
            seconds = parse_duration(value)
            if seconds is not None:
                return max(1, round(seconds))
    delay = _google_retry_delay(getattr(exc, "details", None))
    if delay is not None:
        return delay
    match = _RETRY_IN.search(text)
    if match:
        seconds = parse_duration(match.group(1).rstrip("."))
        if seconds is not None:
            return max(1, round(seconds))
    return None


def _google_retry_delay(details: object) -> int | None:
    """Google error bodies carry {"details": [{"@type": "…RetryInfo", "retryDelay": "41s"}]}."""
    if not isinstance(details, dict):
        return None
    error = details.get("error", details)
    entries = error.get("details") if isinstance(error, dict) else None
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("@type", "")).endswith("RetryInfo"):
            seconds = parse_duration(str(entry.get("retryDelay", "")))
            if seconds is not None:
                return max(1, round(seconds))
    return None
