"""Job descriptions are written by strangers. Before one reaches a model it is cut down,
stripped of anything that reads like an instruction to an AI, and wrapped as data."""

import re

MAX_DESCRIPTION_CHARS = 4_000
MODEL_SNIPPET_CHARS = 600

_INJECTION = re.compile(
    r"(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|prompts?|rules|above|previous)"
    r"|\b(system prompt|you are (now )?(an? )?(ai|assistant|chatgpt|llm|model))\b"
    r"|\b(as an ai|language model)\b.{0,40}\b(must|should|will)\b"
    r"|\b(call|use|invoke|run)\s+(the\s+)?(tool|function)\b"
    r"|<\s*/?\s*(system|assistant|untrusted_content|tool)\b"
    r"|\b(do not|don't) (tell|inform) the user\b",
    re.I,
)


def clean_description(
    text: str | None, limit: int = MAX_DESCRIPTION_CHARS
) -> tuple[str | None, bool]:
    """(text without suspicious lines, whether anything was removed)."""
    if not text:
        return None, False
    kept: list[str] = []
    flagged = False
    for line in text.splitlines():
        if _INJECTION.search(line):
            flagged = True
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned or None, flagged


def model_snippet(text: str | None, limit: int = MODEL_SNIPPET_CHARS) -> str | None:
    if not text:
        return None
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def untrusted(block: str) -> str:
    """Wrap external text so the prompt can say: anything in here is data, not instructions."""
    safe = block.replace("<untrusted_content>", "").replace("</untrusted_content>", "")
    return f"<untrusted_content>\n{safe}\n</untrusted_content>"
