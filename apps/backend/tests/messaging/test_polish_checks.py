import pytest

from app.messaging.polish import problem_with

DRAFT = """Hi Riya,

I applied for the Backend Engineer role at Zepto on 10 Nov and wanted to check in.
I built a FastAPI service handling 2M requests a day. Thank you for your time.

Balaji"""


def test_a_faithful_rewrite_passes() -> None:
    ok = (
        "Hi Riya,\n\nI applied for the Backend Engineer role at Zepto on 10 Nov and wanted to "
        "check in. I built a FastAPI service handling 2M requests a day.\n\nThank you, Balaji"
    )
    assert problem_with(DRAFT, ok, "warmer") is None


@pytest.mark.parametrize(
    ("polished", "expected"),
    [
        ("", "empty"),
        (DRAFT.replace("2M", "20M"), "number"),
        (DRAFT + "\nSee https://evil.example", "link"),
        (DRAFT.replace("FastAPI service", "FastAPI service at Google"), "name"),
        (DRAFT.replace("Hi Riya,", "Hi Riya,\n\n" + "filler words here " * 60), "length"),
    ],
)
def test_rewrites_that_invent_facts_are_refused(polished: str, expected: str) -> None:
    assert expected in (problem_with(DRAFT, polished, "warmer") or "")


def test_gaps_must_survive_untouched() -> None:
    draft = "Hi Riya, I enjoyed learning about [[something specific you discussed]]. Thanks, Balaji"
    assert problem_with(draft, draft.replace("Hi Riya", "Hello Riya"), "warmer") is None
    gone = "Hi Riya, I enjoyed the call very much indeed. Thanks, Balaji"
    assert "gaps" in (problem_with(draft, gone, "warmer") or "")


def test_shorter_must_actually_be_shorter() -> None:
    assert "not shorter" in (problem_with(DRAFT, DRAFT + "\n\nThanks again.", "shorter") or "")
    assert (
        problem_with(
            DRAFT,
            "Hi Riya, I applied for the Backend Engineer role at Zepto on 10 Nov.\n\nBalaji",
            "shorter",
        )
        is None
    )


def test_ordinary_capitals_do_not_trigger_the_name_check() -> None:
    polite = DRAFT.replace("Balaji", "Warm regards, Balaji").replace("Hi Riya", "Hello Riya")
    assert problem_with(DRAFT, polite, "warmer") is None
    sneaky = DRAFT.replace("a FastAPI service", "a FastAPI service for Flipkart")
    assert "name" in (problem_with(DRAFT, sneaky, "warmer") or "")
    assert problem_with(DRAFT, DRAFT.replace("Hi Riya", "Hello Riya"), "warmer") is None
