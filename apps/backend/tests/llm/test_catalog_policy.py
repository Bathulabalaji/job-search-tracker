import pytest

from app.llm.catalog import DEFAULT_MODELS, ModelKind, Provider, load_catalog
from app.llm.policy import DEFAULT_POLICY, LARGE_VARIANT, Task, load_policy


def test_default_policy_only_names_catalog_models_that_fit_the_task() -> None:
    catalog = load_catalog()
    for task, models in DEFAULT_POLICY.items():
        assert models, task
        for name in models:
            spec = catalog.get(name)
            if task is Task.injection_screen:
                assert spec.kind is ModelKind.classifier
            else:
                assert spec.is_chat and spec.supports_tools
    assert catalog.get(DEFAULT_POLICY[Task.chat_agent][0]).provider is Provider.groq
    large = DEFAULT_POLICY[Task.chat_agent_large]
    assert all(catalog.get(m).provider is Provider.google for m in large)
    assert LARGE_VARIANT[Task.chat_agent] is Task.chat_agent_large


def test_groq_prompts_stay_far_below_the_context_window() -> None:
    for spec in DEFAULT_MODELS:
        if spec.provider is Provider.groq and spec.is_chat:
            assert spec.max_prompt_tokens <= spec.tpm  # a single prompt can never exhaust TPM
            assert spec.max_prompt_tokens < spec.context_window


def test_overrides_change_fields_and_can_add_models() -> None:
    catalog = load_catalog(
        '{"openai/gpt-oss-120b": {"rpm": 5, "tpm": 1000},'
        ' "llama-4-new": {"provider": "groq", "rpd": 10}}'
    )
    llama = catalog.get("openai/gpt-oss-120b")
    assert (llama.rpm, llama.tpm, llama.rpd) == (5, 1000, 1_000)  # untouched fields stay
    assert catalog.get("llama-4-new").provider is Provider.groq
    assert "llama-4-new" in catalog


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("{not json", "not valid JSON"),
        ('["a"]', "JSON object keyed by model name"),
        ('{"openai/gpt-oss-120b": 5}', "must be an object"),
        ('{"openai/gpt-oss-120b": {"rpmx": 5}}', "rpmx"),
        ('{"brand-new": {"rpm": 5}}', "needs a 'provider'"),
    ],
)
def test_bad_overrides_are_rejected_with_a_clear_message(raw: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_catalog(raw)


def test_policy_override_replaces_one_task_only() -> None:
    catalog = load_catalog()
    policy = load_policy('{"guardrail": ["gemini-3.5-flash-lite"]}', catalog)
    assert policy[Task.guardrail] == ("gemini-3.5-flash-lite",)
    assert policy[Task.chat_agent] == DEFAULT_POLICY[Task.chat_agent]


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ('{"nope": ["x"]}', "unknown task"),
        ('{"guardrail": "gemini-3.5-flash-lite"}', "list of models"),
        ('{"guardrail": ["no-such-model"]}', "unknown model"),
        ("[]", "JSON object keyed by task"),
    ],
)
def test_bad_policy_overrides_are_rejected(raw: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_policy(raw, load_catalog())
