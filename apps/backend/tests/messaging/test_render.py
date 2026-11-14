import pytest

from app.messaging.catalog import (
    KNOWN_FIELDS,
    LINKEDIN_NOTE_MAX_CHARS,
    MAX_EMAIL_WORDS,
    MAX_LINKEDIN_WORDS,
    TEMPLATES,
)
from app.messaging.render import check_syntax, gaps_in, render, variables_in


def test_fills_values_and_marks_gaps() -> None:
    out = render("Hi {{name}}, about {{role}}.", {"name": "Riya"})
    assert out.text == "Hi Riya, about [[role]]."
    assert [(m.name, m.label) for m in out.missing] == [("role", "role")]
    assert gaps_in(out.text) == ["role"]


def test_a_gap_is_reported_once_however_often_it_appears() -> None:
    out = render("{{role}} and {{role}}", {})
    assert len(out.missing) == 1 and out.text.count("[[role]]") == 2


def test_fallback_is_used_without_a_gap() -> None:
    out = render("Hi {{recipient_first|there}},", {})
    assert out.text == "Hi there," and out.missing == []


def test_optional_sections_disappear_when_empty() -> None:
    template = "A.{{?proof_point}} {{proof_point}}{{/}}{{?bridge}} {{bridge}}{{/}} B."
    assert render(template, {}).text == "A. B."
    assert render(template, {"proof_point": "Cut latency 40%."}).text == "A. Cut latency 40%. B."
    assert render(template, {}).missing == []


def test_values_cannot_inject_template_syntax_or_control_characters() -> None:
    out = render("Hi {{name}}.", {"name": "{{company}}\x00\x07 Rao"})
    assert "{{" not in out.text and "\x00" not in out.text and "Rao" in out.text
    assert render("Subject: {{s}}", {"s": "a\nb\r\nc"}, single_line=True).text == "Subject: a b c"


def test_collapses_blank_runs_and_stray_spaces_before_punctuation() -> None:
    assert render("A {{x}} .\n\n\n\nB", {"x": ""}, single_line=False).text.count("\n\n\n") == 0
    assert render("Hello {{?x}}{{x}}{{/}}, there", {}).text == "Hello, there"


@pytest.mark.parametrize(
    ("template", "problem"),
    [
        ("{{?a}}no end", "missing its"),
        ("text {{/}}", "never opened"),
        ("{{?a}}{{?b}}x{{/}}{{/}}", "nested"),
        ("hello {{Bad Name}}", "stray"),
        ("hello {{ name", "stray"),
    ],
)
def test_syntax_problems_are_explained(template: str, problem: str) -> None:
    assert problem in (check_syntax(template) or "")


def test_well_formed_templates_pass_the_syntax_check() -> None:
    assert check_syntax("Hi {{a}} {{b|c}} {{?d}}x{{/}}") is None


# ---- the built-in library -------------------------------------------------------------------

FULL = {name: f"<{name}>" for name in KNOWN_FIELDS}


def _variants() -> list[tuple[str, str, str | None, str]]:
    return [(t.key, v.channel, v.subject, v.body) for t in TEMPLATES for v in t.variants]


@pytest.mark.parametrize(("key", "channel", "subject", "body"), _variants())
def test_every_template_is_well_formed(
    key: str, channel: str, subject: str | None, body: str
) -> None:
    for text in (body, subject or ""):
        assert check_syntax(text) is None, f"{key}/{channel}"
        assert variables_in(text) <= KNOWN_FIELDS, (
            f"{key}/{channel}: {variables_in(text) - KNOWN_FIELDS}"
        )
    if channel == "email":
        assert subject, f"{key}: an email needs a subject"
    else:
        assert subject is None, f"{key}: only email has a subject"
    assert "Sir/Madam" not in body and "Dear Sir" not in body


@pytest.mark.parametrize(("key", "channel", "subject", "body"), _variants())
def test_templates_stay_short_and_ask_for_one_thing(
    key: str, channel: str, subject: str | None, body: str
) -> None:
    sparse = render(body, {"signature": ""}).text
    words = len(sparse.split())
    limit = MAX_EMAIL_WORDS if channel == "email" else MAX_LINKEDIN_WORDS
    assert words <= limit, f"{key}/{channel} is {words} words (limit {limit})"
    assert sparse.count("?") <= 2, f"{key}/{channel} asks too many questions"


def test_the_connection_note_fits_even_when_fully_filled() -> None:
    note = next(v for t in TEMPLATES for v in t.variants if v.channel == "linkedin_note")
    worst = {
        "recipient_first": "Venkatasubramanian",
        "headline": "a senior software engineer with 12 years of experience in payments",
        "role": "Senior Backend Engineer",
        "company": "Hindustan Unilever Limited",
        "my_first_name": "Balasubramanian",
    }
    assert len(render(note.body, worst).text) <= LINKEDIN_NOTE_MAX_CHARS


def test_template_keys_are_unique_and_cover_every_group() -> None:
    keys = [t.key for t in TEMPLATES]
    assert len(keys) == len(set(keys)) == 14
    assert {t.group for t in TEMPLATES} == {
        "reach_out", "after_applying", "screening", "interviewing", "offer", "closing",
    }  # fmt: skip
