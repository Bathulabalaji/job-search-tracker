"""Task -> ordered list of candidate models.

Order is preference. The ledger then drops any candidate that is over budget, cooling down or
has an open circuit, so what actually answers depends on the minute. LLM_POLICY_OVERRIDE
replaces the list for any task.
"""

import json
from enum import StrEnum

from app.llm.catalog import Catalog


class Task(StrEnum):
    chat_agent = "chat.agent"  # the tool-calling turn of a conversation
    chat_agent_large = "chat.agent.large"  # same, for prompts too big for the Groq tier
    guardrail = "guardrail"  # scope/intent verdict before the agent runs
    injection_screen = "injection_screen"  # classify fetched text before the model sees it
    summarize = "summarize"  # rolling conversation summary, tool-result compaction
    extract_structured = "extract.structured"  # resume profile, match scoring (JSON schema)


Policy = dict[Task, tuple[str, ...]]

DEFAULT_POLICY: Policy = {
    Task.chat_agent: (
        "openai/gpt-oss-120b",  # strong reasoning and tool calling on Groq's free tier
        "qwen/qwen3.8-27b",  # its own Groq budget; tool-call formatting is less consistent
        "gemini-3.5-flash-lite",  # big per-minute budget: sustained traffic lands here
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",  # best quality, smallest daily budget: spill-over only
    ),
    Task.chat_agent_large: ("gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"),
    Task.guardrail: ("openai/gpt-oss-20b", "gemini-3.5-flash-lite"),
    Task.injection_screen: ("meta-llama/llama-prompt-guard-2-86m",),
    Task.summarize: ("openai/gpt-oss-20b", "gemini-3.5-flash-lite"),
    Task.extract_structured: (
        "gemini-3.5-flash-lite",  # native JSON schema mode and room for long inputs
        "gemini-3.1-flash-lite",
        "openai/gpt-oss-120b",
    ),
}

# When a prompt will not fit the task's usual models, use this task instead.
LARGE_VARIANT: dict[Task, Task] = {Task.chat_agent: Task.chat_agent_large}


def large_prompt_threshold(task: Task, policy: Policy, catalog: Catalog) -> int | None:
    """Prompts above this many tokens go straight to the task's large variant.

    It is the smallest prompt budget among the task's candidates: a prompt that cannot fit
    the Groq tier belongs with the models chosen for long context, in their own order.
    """
    if task not in LARGE_VARIANT:
        return None
    sizes = [catalog.get(name).max_prompt_tokens for name in policy.get(task, ())]
    return min(sizes) if sizes else None


def load_policy(override_json: str, catalog: Catalog) -> Policy:
    policy: Policy = dict(DEFAULT_POLICY)
    if override_json.strip():
        try:
            raw = json.loads(override_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM_POLICY_OVERRIDE is not valid JSON: {exc.msg}") from exc
        if not isinstance(raw, dict):
            raise ValueError("LLM_POLICY_OVERRIDE must be a JSON object keyed by task")
        for task_name, models in raw.items():
            try:
                task = Task(task_name)
            except ValueError:
                raise ValueError(
                    f"LLM_POLICY_OVERRIDE: unknown task {task_name!r}; "
                    f"tasks: {[t.value for t in Task]}"
                ) from None
            if not isinstance(models, list) or not all(isinstance(m, str) for m in models):
                raise ValueError(f"LLM_POLICY_OVERRIDE[{task_name!r}] must be a list of models")
            policy[task] = tuple(models)
    for task, models in policy.items():
        for model in models:
            if model not in catalog:
                raise ValueError(f"policy for {task.value!r} names unknown model {model!r}")
    return policy
