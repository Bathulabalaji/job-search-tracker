"""One place that turns HTTP outcomes into ProviderError kinds."""

from typing import Any

import httpx

from app.jobsearch.base import ProviderError


def get_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    timeout: float,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        response = client.request(
            method, url, params=params, json=json, headers=headers, timeout=timeout
        )
    except httpx.TimeoutException as exc:
        raise ProviderError("unavailable", "timeout") from exc
    except httpx.HTTPError as exc:
        raise ProviderError("unavailable", type(exc).__name__) from exc
    status = response.status_code
    if status in (402, 429):
        raise ProviderError("quota", str(status))
    if status in (401, 403):
        # RapidAPI answers 403 "not subscribed" and 429 for the monthly cap.
        raise ProviderError("auth", str(status))
    if status >= 500:
        raise ProviderError("unavailable", str(status))
    if status >= 400:
        raise ProviderError("bad_request", str(status))
    try:
        body = response.json()
    except ValueError as exc:
        raise ProviderError("unavailable", "invalid json") from exc
    if not isinstance(body, dict):
        raise ProviderError("unavailable", "unexpected body")
    return body


def text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
