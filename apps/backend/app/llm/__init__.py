"""The LLM gateway: one place that talks to AI providers for the whole app.

`build_llm_gateway(settings, session, clock)` wires the configured providers, the model
catalog, the routing policy and the shared budget ledger together. Services call
`gateway.chat(task, messages, ...)` or `gateway.embed(texts)` and never see a provider SDK.
"""

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.llm.catalog import Provider, load_catalog
from app.llm.gateway import LLMGateway
from app.llm.ledger import BudgetLedger
from app.llm.policy import load_policy
from app.llm.providers.base import ChatProvider


def build_providers(settings: Settings) -> dict[Provider, ChatProvider]:
    """Only providers with a key are built; the SDK modules load lazily, keeping startup light."""
    providers: dict[Provider, ChatProvider] = {}
    if settings.groq_api_key:
        from app.llm.providers.groq import groq_provider

        providers[Provider.groq] = groq_provider(settings.groq_api_key)
    if settings.google_ai_api_key:
        from app.llm.providers.google import google_provider

        providers[Provider.google] = google_provider(settings.google_ai_api_key)
    return providers


def build_llm_gateway(
    settings: Settings,
    session: Session,
    clock: Clock,
    *,
    user_id: int | None = None,
    providers: dict[Provider, ChatProvider] | None = None,
) -> LLMGateway:
    catalog = load_catalog(settings.llm_model_limits)
    policy = load_policy(settings.llm_policy_override, catalog)
    ledger = BudgetLedger(
        session,
        clock,
        catalog,
        circuit_failures=settings.llm_circuit_failures,
        circuit_cooldown_seconds=settings.llm_circuit_cooldown_seconds,
    )
    return LLMGateway(
        ledger=ledger,
        providers=providers if providers is not None else build_providers(settings),
        policy=policy,
        catalog=catalog,
        clock=clock,
        request_timeout=settings.llm_request_timeout_seconds,
        run_timeout=settings.llm_run_timeout_seconds,
        max_switches=settings.llm_max_model_switches,
        embedding_model=settings.embedding_model,
        embedding_dims=settings.embedding_dims,
        user_id=user_id,
    )


__all__ = ["LLMGateway", "build_llm_gateway", "build_providers"]
