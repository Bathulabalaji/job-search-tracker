"""SDK exceptions never reach callers: everything becomes an `LLMError` with a stable code.

The stand-in exceptions below mirror the *shape* of the Groq and Google SDK errors (status
codes, response headers, error bodies) without importing those SDKs' classes, which is also
how the classifier itself works, so a provider SDK upgrade cannot silently break the mapping.
"""

import httpx
import pytest
from langchain_core.exceptions import (
    ContextOverflowError,
    ModelAuthenticationError,
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
from app.llm.providers.classify import classify_exception


class GroqLikeStatusError(Exception):
    """Shaped like groq.APIStatusError: status_code, message and a response with headers."""

    def __init__(self, status_code: int, message: str, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        request = httpx.Request("POST", "https://api.groq.com")
        self.response = httpx.Response(status_code, headers=headers or {}, request=request)


class GoogleLikeClientError(Exception):
    """Shaped like google.genai.errors.ClientError: code, status, message, details (the body)."""

    def __init__(self, code: int, status: str, message: str, details: object) -> None:
        super().__init__(f"{code} {status}. {message}")
        self.code = code
        self.status = status
        self.message = message
        self.details = details


def classify(exc: BaseException) -> LLMError:
    return classify_exception(exc, provider="test", model="m")


def test_groq_minute_rate_limit_keeps_headers_and_retry_after() -> None:
    exc = GroqLikeStatusError(
        429,
        "Rate limit reached for model `openai/gpt-oss-120b` on tokens per minute (TPM): "
        "Limit 6000, Used 5000, Requested 1500. Please try again in 3.2s.",
        {"retry-after": "4", "x-ratelimit-remaining-tokens": "0", "content-type": "text"},
    )
    error = classify(exc)
    assert isinstance(error, RateLimited)
    assert (error.kind, error.retry_after) == ("minute", 4)
    assert error.headers == {"retry-after": "4", "x-ratelimit-remaining-tokens": "0"}
    assert (error.provider, error.model, error.status_code) == ("test", "m", 429)


def test_groq_daily_limit_is_a_day_quota_with_the_delay_from_the_message() -> None:
    message = (
        "Rate limit reached on requests per day (RPD): Limit 1000. Please try again in 2h3m4s."
    )
    error = classify(GroqLikeStatusError(429, message))
    assert isinstance(error, RateLimited) and error.kind == "day"
    assert error.retry_after == 2 * 3600 + 3 * 60 + 4


def test_google_rate_limit_reads_retry_info_and_quota_id() -> None:
    body = {
        "error": {
            "code": 429,
            "message": "You exceeded your current quota",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel"}],
                },
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "41s"},
            ],
        }
    }
    cause = GoogleLikeClientError(429, "RESOURCE_EXHAUSTED", "quota", body)
    wrapped = ModelRateLimitError("Error calling model 'gemini' (RESOURCE_EXHAUSTED)")
    wrapped.__cause__ = cause
    error = classify(wrapped)
    assert isinstance(error, RateLimited)
    assert (error.kind, error.retry_after) == ("day", 41)


CONTEXT_MESSAGE = "Please reduce the length of the messages or completion."


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (GroqLikeStatusError(401, "Invalid API Key"), ProviderAuthFailed),
        (GroqLikeStatusError(403, "forbidden"), ProviderAuthFailed),
        (ModelAuthenticationError("bad key"), ProviderAuthFailed),
        (GroqLikeStatusError(400, CONTEXT_MESSAGE), ContextTooLong),
        (ContextOverflowError("exceeds the maximum number of tokens allowed"), ContextTooLong),
        (
            GroqLikeStatusError(400, "json_schema response_format is not supported"),
            ProviderBadRequest,
        ),
        (GroqLikeStatusError(404, "model not found"), ProviderBadRequest),
        (GroqLikeStatusError(400, "content_filter: blocked"), ContentBlocked),
        (ModelRefusalError("refused"), ContentBlocked),
        (GroqLikeStatusError(503, "Service Unavailable"), ProviderUnavailable),
        (GroqLikeStatusError(500, "internal"), ProviderUnavailable),
        (RuntimeError("something odd"), ProviderUnavailable),
    ],
)
def test_status_codes_and_standard_errors_map_to_the_taxonomy(
    exc: Exception, expected: type[LLMError]
) -> None:
    assert isinstance(classify(exc), expected)


def test_timeouts_and_connection_errors_are_marked_as_such() -> None:
    timeout = classify(httpx.ReadTimeout("read timed out"))
    assert isinstance(timeout, ProviderUnavailable) and timeout.kind == "timeout"
    assert isinstance(classify(ModelTimeoutError("slow")), ProviderUnavailable)
    connect = classify(httpx.ConnectError("refused"))
    assert isinstance(connect, ProviderUnavailable) and connect.kind == "connection"


def test_details_never_leak_into_the_user_message() -> None:
    error = classify(GroqLikeStatusError(500, "stack trace with org_abc123 and key sk-xyz"))
    assert "org_abc123" in error.detail
    assert "org_abc123" not in error.user_message
