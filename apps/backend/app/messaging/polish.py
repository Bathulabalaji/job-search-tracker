"""Checks on an AI rewrite of a message. The model may rephrase; it may not invent.

A job seeker's message names employers, numbers and skills. A rewrite that adds one that the
draft did not contain would put a false claim in front of a recruiter, so such a rewrite is
refused and the original is kept.
"""

import re
from collections import Counter

from app.messaging.render import gaps_in

INSTRUCTIONS: dict[str, str] = {
    "shorter": "Make it clearly shorter by cutting filler. Keep the ask and the proof point.",
    "warmer": (
        "Make the tone warmer and friendlier with softer wording, still professional. Do not "
        "add new statements about what the writer has done, read, followed or feels."
    ),
    "more_formal": "Make the tone more formal and polished.",
    "more_direct": "Make it more direct: lead with the ask, remove hedging.",
    "fix_grammar": "Fix spelling, grammar and punctuation only. Keep the wording otherwise.",
}

_NUMBER = re.compile(r"\d[\d,.]*")
_LINK = re.compile(r"https?://\S+|\b[\w.+-]+@[\w-]+\.[\w.-]+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
# Words that start or close a message and carry no facts, so adding them is never an invention.
_SAFE = {
    "i", "i'm", "i’m", "i'd", "i’d", "i've", "i’ve", "i'll", "i’ll",
    "thanks", "thank", "regards", "best", "sincerely", "cheers", "warm", "kind", "please",
    "hello", "hi", "dear", "appreciate", "looking", "grateful",
}  # fmt: skip


def _words(text: str) -> int:
    return len(text.split())


def _new_names(original: str, polished: str) -> list[str]:
    known = {w.lower() for w in _WORD.findall(original)}
    new: list[str] = []
    for sentence in _SENTENCE.split(polished):
        words = _WORD.findall(sentence)
        for word in words[1:]:  # the first word is capitalised anyway
            if word[0].isupper() and word.lower() not in known and word.lower() not in _SAFE:
                new.append(word)
    return new


def problem_with(original: str, polished: str, instruction: str) -> str | None:
    """A short reason the rewrite can't be used, or None when it is safe."""
    if not polished.strip():
        return "The rewrite came back empty."
    if Counter(gaps_in(original)) != Counter(gaps_in(polished)):
        return "The rewrite changed the [[gaps]] you still need to fill in."
    if set(_NUMBER.findall(polished)) - set(_NUMBER.findall(original)):
        return "The rewrite added a number that was not in your draft."
    if {x.lower() for x in _LINK.findall(polished)} - {x.lower() for x in _LINK.findall(original)}:
        return "The rewrite added a link or email address."
    invented = _new_names(original, polished)
    if invented:
        return f"The rewrite introduced a name your draft did not contain ({invented[0]})."
    before, after = _words(original), _words(polished)
    if before and not 0.4 <= after / before <= 1.4:
        return "The rewrite changed the length too much."
    if instruction == "shorter" and after >= before:
        return "The rewrite was not shorter."
    return None
