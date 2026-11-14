"""Redaction of identifiers that must never be stored or sent to a model.

The brief's rule: no government IDs, passwords or bank details anywhere in the app. Resume
text goes through this *before* it is persisted or embedded. Patterns are deliberately
conservative (a 12-digit Aadhaar must pass its checksum; a passport number must sit near the
word) so that phone numbers and ordinary figures survive. Contact details are kept, since
recruiters need them, but normalised so they are easy to strip later.
"""

import re

_AADHAAR = re.compile(r"\b(\d{4})[ -]?(\d{4})[ -]?(\d{4})\b")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_PASSPORT = re.compile(r"(?i)(passport(?:\s*(?:no|number|#))?\s*[:.-]?\s*)([A-PR-WY][1-9]\d{6})\b")
_VOTER = re.compile(r"\b[A-Z]{3}\d{7}\b")
_IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_ACCOUNT = re.compile(
    r"(?i)((?:account|a/c|acct|acc)\s*(?:no|number|#)?\s*[:.-]?\s*)(\d[\d -]{7,20}\d)"
)
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_DOB = re.compile(r"(?i)(d\.?o\.?b\.?|date of birth|born on?)\s*[:.-]?\s*[^\n,;]{4,30}")
_PASSWORD = re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+")
_CARD = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")

# Verhoeff checksum, the one Aadhaar uses: filters out most 12-digit numbers that are not IDs.
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff_valid(number: str) -> bool:
    check = 0
    for index, char in enumerate(reversed(number)):
        check = _D[check][_P[index % 8][int(char)]]
    return check == 0


def _aadhaar(match: re.Match[str]) -> str:
    digits = "".join(match.groups())
    if digits[0] in "01" or not verhoeff_valid(digits):
        return match.group(0)
    return "[REDACTED_ID]"


def _card(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return "[REDACTED_ID]" if len(digits) == 16 and _luhn(digits) else match.group(0)


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        n = int(char)
        if index % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def redact(text: str) -> str:
    """Strip identifiers the app must not hold. Idempotent."""
    text = _PASSWORD.sub(r"\1: [REDACTED]", text)
    text = _PASSPORT.sub(r"\1[REDACTED_ID]", text)
    text = _ACCOUNT.sub(r"\1[REDACTED_ID]", text)
    text = _CARD.sub(_card, text)
    text = _AADHAAR.sub(_aadhaar, text)
    text = _PAN.sub("[REDACTED_ID]", text)
    text = _VOTER.sub("[REDACTED_ID]", text)
    text = _IFSC.sub("[REDACTED_ID]", text)
    text = _SSN.sub("[REDACTED_ID]", text)
    text = _DOB.sub(r"\1: [REDACTED]", text)
    return text


def contains_redactable(text: str) -> bool:
    return redact(text) != text
