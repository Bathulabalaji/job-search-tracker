"""Fill a template with the facts of one opportunity. Pure code, no eval, trivially tested.

Grammar (deliberately tiny, so a template can never run code):
  {{name}}            the value; if there is none, a visible gap  [[what to fill in]]
  {{name|fallback}}   the value, or the fallback text when there is none (never a gap)
  {{?name}}...{{/}}   the enclosed text only when `name` has a value (no gap otherwise)

A value is never interpreted again: braces inside a recruiter's name or a job title are
defanged, and control characters are removed, so data can't inject template syntax.
"""

import re
from dataclasses import dataclass, field

# What the user sees (and is asked to fill in) when a value is missing.
LABELS: dict[str, str] = {
    "recipient_first": "recipient's first name",
    "my_name": "your name",
    "my_first_name": "your first name",
    "my_email": "your email",
    "headline": "your one-line introduction",
    "proof_point": "one achievement",
    "skills": "your key skills",
    "my_location": "your current location",
    "notice_period": "your notice period",
    "current_ctc": "your current CTC",
    "expected_ctc": "your expected CTC",
    "availability": "when you are available",
    "talking_point": "something specific you discussed",
    "new_update": "something new since your last message",
    "decision_date": "the date you'll decide by",
    "company": "company",
    "role": "role",
    "applied_when": "when you applied",
    "round_label": "which interview",
    "signature": "your signature",
}

_TOKEN = re.compile(r"\{\{(\?)?\s*([a-z_]+)\s*(?:\|([^{}]*))?\}\}|\{\{/\}\}")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLANK_RUNS = re.compile(r"\n{3,}")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?])")
GAP = re.compile(r"\[\[([^\[\]\n]+)\]\]")


@dataclass(frozen=True)
class Missing:
    name: str
    label: str


@dataclass
class Rendered:
    text: str
    missing: list[Missing] = field(default_factory=list)


def clean_value(value: object) -> str:
    """One merge value as safe text: no control characters, no template syntax."""
    text = _CONTROL.sub("", str(value or "")).strip()
    return text.replace("{{", "{ {").replace("}}", "} }")


def variables_in(template: str) -> set[str]:
    """Every field name a template mentions (used to reject unknown names when saving)."""
    return {m.group(2) for m in _TOKEN.finditer(template) if m.group(2)}


def check_syntax(template: str) -> str | None:
    """A readable problem with the template's braces, or None when it is well formed."""
    depth = 0
    for match in _TOKEN.finditer(template):
        if match.group(0) == "{{/}}":
            depth -= 1
            if depth < 0:
                return "A {{/}} closes a section that was never opened."
        elif match.group(1):
            depth += 1
            if depth > 1:
                return "Sections can't be nested."
    if depth != 0:
        return "A {{?name}} section is missing its {{/}}."
    stripped = _TOKEN.sub("", template)
    if "{{" in stripped or "}}" in stripped:
        return "There is a stray {{ or }} (names use lowercase letters and underscores)."
    return None


def render(template: str, values: dict[str, str], *, single_line: bool = False) -> Rendered:
    """`values` maps field name to text; empty or absent means missing."""
    missing: list[Missing] = []
    seen: set[str] = set()
    out: list[str] = []
    skipping = False
    pos = 0
    for match in _TOKEN.finditer(template):
        if not skipping:
            out.append(template[pos : match.start()])
        pos = match.end()
        if match.group(0) == "{{/}}":
            skipping = False
            continue
        name, fallback = match.group(2), match.group(3)
        value = clean_value(values.get(name, ""))
        if match.group(1):  # {{?name}} opens an optional section
            skipping = not value
            continue
        if skipping:
            continue
        if value:
            out.append(value)
        elif fallback is not None:
            out.append(fallback.strip())
        else:
            label = LABELS.get(name, name.replace("_", " "))
            out.append(f"[[{label}]]")
            if name not in seen:
                seen.add(name)
                missing.append(Missing(name, label))
    if not skipping:
        out.append(template[pos:])
    text = "".join(out)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    if single_line:
        text = " ".join(text.split())
    else:
        text = _BLANK_RUNS.sub("\n\n", text)
    return Rendered(text.strip(), missing)


def gaps_in(text: str) -> list[str]:
    """Placeholders still left in a draft, e.g. before it is sent."""
    return [m.group(1) for m in GAP.finditer(text)]
