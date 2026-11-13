"""`LLMError`s raised anywhere under the API become `{detail, code}` bodies with the right
status, a Retry-After header when there is a wait, and never the provider detail."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.llm.errors import AllModelsExhausted, ContextTooLong, ProviderUnavailable
from app.main import app

ROUTE = "/api/v1/_tests/llm-error"
_SCENARIOS: dict[str, Exception] = {
    "capacity": AllModelsExhausted("org_abc quota detail", retry_after=120),
    "unavailable": ProviderUnavailable("502 from provider"),
    "context": ContextTooLong("too long"),
}


@pytest.fixture(scope="module", autouse=True)
def _route() -> Iterator[None]:
    def raise_llm_error(scenario: str) -> None:
        raise _SCENARIOS[scenario]

    app.add_api_route(ROUTE, raise_llm_error, methods=["GET"])
    yield
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != ROUTE]


def test_capacity_errors_are_429_with_retry_after(client: TestClient) -> None:
    response = client.get(ROUTE, params={"scenario": "capacity"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "120"
    body = response.json()
    assert body["code"] == "assistant_capacity"
    assert "2 minutes" in body["detail"]
    assert "org_abc" not in response.text


def test_provider_outages_are_503_with_the_generic_message(client: TestClient) -> None:
    response = client.get(ROUTE, params={"scenario": "unavailable"})
    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI provider is having trouble. Please try again in a minute.",
        "code": "assistant_unavailable",
    }
    assert "Retry-After" not in response.headers


def test_context_errors_are_400(client: TestClient) -> None:
    response = client.get(ROUTE, params={"scenario": "context"})
    assert response.status_code == 400
    assert response.json()["code"] == "assistant_context_too_long"
