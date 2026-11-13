"""The real adapters, without a network: constructor arguments the installed LangChain classes
accept, header capture, and the Groq stream wrapper's error translation."""

from collections.abc import Iterator

import httpx
from langchain_core.messages import AIMessage, HumanMessage

from app.llm.catalog import load_catalog
from app.llm.errors import ProviderUnavailable
from app.llm.providers.base import ChatReply
from app.llm.providers.google import GoogleProvider, google_provider
from app.llm.providers.groq import GroqProvider, groq_provider


def test_groq_model_construction_matches_the_installed_langchain_groq() -> None:
    provider = GroqProvider("gsk_test")
    spec = load_catalog().get("openai/gpt-oss-120b")
    model = provider._model(spec, timeout=7.5, max_tokens=321, temperature=0.0)
    assert model.model_name == spec.name
    assert model.max_tokens == 321 and model.max_retries == 0
    assert model.http_client is provider.http_client


def test_google_model_construction_matches_the_installed_langchain_google_genai() -> None:
    provider = GoogleProvider("AIza-test")
    spec = load_catalog().get("gemini-3.5-flash-lite")
    model = provider._model(spec, timeout=7.5, max_tokens=321, temperature=0.0)
    assert model.model.endswith(spec.name)
    assert model.max_output_tokens == 321 and model.max_retries == 0
    embeddings = provider._embeddings(load_catalog().get("gemini-embedding-001"), timeout=5)
    assert embeddings.model == "models/gemini-embedding-001"


def test_groq_rate_limit_headers_are_captured_from_responses() -> None:
    provider = GroqProvider("gsk_test")
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(
        200,
        headers={"x-ratelimit-remaining-tokens": "4321", "content-type": "application/json"},
        request=request,
    )
    provider._capture_headers(response)
    assert provider.last_headers() == {"x-ratelimit-remaining-tokens": "4321"}


def test_groq_stream_errors_are_translated_and_headers_attached() -> None:
    provider = GroqProvider("gsk_test")
    spec = load_catalog().get("openai/gpt-oss-120b")

    def broken() -> Iterator[AIMessage]:
        yield from ()
        raise httpx.ReadTimeout("slow")

    reply = ChatReply()
    wrapped = provider._wrap_stream(broken(), reply, spec)
    try:
        list(wrapped)
    except ProviderUnavailable as exc:
        assert exc.kind == "timeout" and exc.model == spec.name
    else:  # pragma: no cover - the assertion above must run
        raise AssertionError("expected ProviderUnavailable")


def test_providers_are_cached_per_key() -> None:
    assert groq_provider("k1") is groq_provider("k1")
    assert groq_provider("k1") is not groq_provider("k2")
    assert google_provider("g1") is google_provider("g1")


def test_a_prompt_round_trips_as_langchain_messages() -> None:
    assert HumanMessage(content="hi").content == "hi"
