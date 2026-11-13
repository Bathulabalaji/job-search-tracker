"""Which models exist, who serves them, and how much of each we may use.

The budgets are the free-tier limits as published or observed on 2026-11-13. They are starting
points, not truth: each provider shows the real figures for *your* account in its console, and
LLM_MODEL_LIMITS overrides any field per model (or adds a model). The ledger also trusts the
rate-limit headers a provider sends over anything written here.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Provider(StrEnum):
    groq = "groq"
    google = "google"


class ModelKind(StrEnum):
    chat = "chat"
    classifier = "classifier"
    embedding = "embedding"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    provider: Provider
    kind: ModelKind = ModelKind.chat
    context_window: int = 131_072
    # The most prompt tokens we hand this model: far below the context window, because on a
    # free tier it is the per-minute token budget, not the window, that runs out first.
    max_prompt_tokens: int = 5_000
    max_completion_tokens: int = 1_024
    # Requests/tokens per minute/day. 0 means "not enforced locally" (headers may still apply).
    rpm: int = 0
    rpd: int = 0
    tpm: int = 0
    tpd: int = 0
    supports_tools: bool = True
    supports_json_schema: bool = True

    @property
    def is_chat(self) -> bool:
        return self.kind == ModelKind.chat


def _groq(name: str, *, rpm: int, rpd: int, tpm: int, tpd: int) -> ModelSpec:
    return ModelSpec(name=name, provider=Provider.groq, rpm=rpm, rpd=rpd, tpm=tpm, tpd=tpd)


def _google(name: str, *, rpm: int, rpd: int, tpm: int, tpd: int = 0) -> ModelSpec:
    return ModelSpec(
        name=name,
        provider=Provider.google,
        context_window=1_048_576,
        max_prompt_tokens=24_000,
        max_completion_tokens=2_048,
        rpm=rpm,
        rpd=rpd,
        tpm=tpm,
        tpd=tpd,
    )


DEFAULT_MODELS: tuple[ModelSpec, ...] = (
    _groq("openai/gpt-oss-120b", rpm=30, rpd=1_000, tpm=8_000, tpd=200_000),
    _groq("openai/gpt-oss-20b", rpm=30, rpd=1_000, tpm=8_000, tpd=200_000),
    _groq("qwen/qwen3.8-27b", rpm=30, rpd=1_000, tpm=8_000, tpd=200_000),
    ModelSpec(
        name="meta-llama/llama-prompt-guard-2-86m",
        provider=Provider.groq,
        kind=ModelKind.classifier,
        context_window=512,
        max_prompt_tokens=480,
        max_completion_tokens=8,
        rpm=30,
        rpd=14_400,
        tpm=15_000,
        tpd=500_000,
        supports_tools=False,
        supports_json_schema=False,
    ),
    # Google does not publish free-tier numbers; these are deliberately conservative.
    _google("gemini-3.8-flash", rpm=10, rpd=250, tpm=250_000),
    _google("gemini-3.5-flash-lite", rpm=15, rpd=1_000, tpm=250_000),
    _google("gemini-3.1-flash-lite", rpm=15, rpd=1_000, tpm=250_000),
    ModelSpec(
        name="gemini-embedding-001",
        provider=Provider.google,
        kind=ModelKind.embedding,
        context_window=2_048,
        max_prompt_tokens=2_048,
        max_completion_tokens=0,
        rpm=100,
        rpd=1_000,
        tpm=30_000,
        supports_tools=False,
        supports_json_schema=False,
    ),
)


class ModelOverride(BaseModel):
    """One entry of LLM_MODEL_LIMITS. `provider` is required only when adding a new model."""

    model_config = ConfigDict(extra="forbid")

    provider: Provider | None = None
    kind: ModelKind | None = None
    context_window: int | None = None
    max_prompt_tokens: int | None = None
    max_completion_tokens: int | None = None
    rpm: int | None = None
    rpd: int | None = None
    tpm: int | None = None
    tpd: int | None = None
    supports_tools: bool | None = None
    supports_json_schema: bool | None = None


class Catalog:
    def __init__(self, models: Iterable[ModelSpec]) -> None:
        self._models = {m.name: m for m in models}

    def get(self, name: str) -> ModelSpec:
        try:
            return self._models[name]
        except KeyError:
            raise KeyError(f"unknown model {name!r}; known: {sorted(self._models)}") from None

    def __contains__(self, name: str) -> bool:
        return name in self._models

    def names(self) -> list[str]:
        return list(self._models)

    def models(self) -> list[ModelSpec]:
        return list(self._models.values())


def parse_overrides(raw_json: str) -> dict[str, ModelOverride]:
    """Validate LLM_MODEL_LIMITS. Raises ValueError with a message fit for startup logs."""
    if not raw_json.strip():
        return {}
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM_MODEL_LIMITS is not valid JSON: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise ValueError("LLM_MODEL_LIMITS must be a JSON object keyed by model name")
    overrides: dict[str, ModelOverride] = {}
    for name, fields in raw.items():
        if not isinstance(fields, dict):
            raise ValueError(f"LLM_MODEL_LIMITS[{name!r}] must be an object")
        overrides[str(name)] = ModelOverride.model_validate(fields)
    return overrides


def load_catalog(overrides_json: str = "") -> Catalog:
    models = {m.name: m for m in DEFAULT_MODELS}
    for name, override in parse_overrides(overrides_json).items():
        fields = override.model_dump(exclude_none=True)
        if name in models:
            models[name] = replace(models[name], **fields)
        elif override.provider is None:
            raise ValueError(f"LLM_MODEL_LIMITS: new model {name!r} needs a 'provider'")
        else:
            models[name] = ModelSpec(name=name, **fields)
    return Catalog(models.values())
