"""Turn an opportunity, a contact and the sender's profile into the values a template uses.

Pure: no database, no clock. The service gathers the facts; this decides the words.
"""

from dataclasses import dataclass, field
from datetime import date

ROUND_LABELS: dict[str, str] = {
    "technical": "technical interview",
    "manager": "conversation with the hiring manager",
    "hr": "HR discussion",
    "screening": "screening call",
}
OVERRIDABLE = frozenset(
    {
        "talking_point", "new_update", "availability", "decision_date", "follow_up_detail",
        "round", "proof_point", "headline", "expected_ctc", "current_ctc", "notice_period",
        "my_location", "bridge", "skills", "applied_when", "recipient_first",
    }
)  # fmt: skip


@dataclass
class Sender:
    name: str
    account_email: str
    from_email: str | None = None
    headline: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    location: str | None = None
    notice_period: str | None = None
    current_ctc: str | None = None
    expected_ctc: str | None = None
    career_story: str | None = None
    proof_points: list[str] = field(default_factory=list)

    @property
    def email(self) -> str:
        return self.from_email or self.account_email


@dataclass
class JobFacts:
    company: str
    role: str
    stack_tags: list[str] = field(default_factory=list)
    applied_on: date | None = None


def _article(phrase: str) -> str:
    return ("an " if phrase[:1].lower() in "aeiou" else "a ") + phrase


def suggest_headline(titles: list[str], years: float | None) -> str | None:
    """A starting point for "I'm ...", from what the user's resumes say about them."""
    title = next((t.strip() for t in titles if t.strip()), "")
    if not title:
        return None
    lowered = title[:1].lower() + title[1:] if title[:2].upper() != title[:2] else title
    if years:
        return f"{_article(lowered)} with {years:g} years of experience"
    return _article(lowered)


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def when_applied(applied_on: date | None, today: date) -> str:
    if applied_on is None:
        return "recently"
    days = (today - applied_on).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"on {applied_on.day} {applied_on:%b}"


def signature(sender: Sender) -> str:
    lines = ["Thanks and regards,", sender.name]
    contact = " | ".join(p for p in (sender.email, sender.phone) if p)
    if contact:
        lines.append(contact)
    if sender.linkedin_url:
        lines.append(sender.linkedin_url)
    return "\n".join(lines)


def build_values(
    *,
    sender: Sender,
    job: JobFacts,
    recipient_name: str | None,
    today: date,
    resume_skills: list[str] | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    skills = _join((job.stack_tags or resume_skills or [])[:3])
    values: dict[str, str] = {
        "my_name": sender.name,
        "my_first_name": sender.name.split()[0] if sender.name.split() else "",
        "my_email": sender.email,
        "headline": sender.headline or "",
        "proof_point": sender.proof_points[0] if sender.proof_points else "",
        "bridge": sender.career_story or "",
        "skills": skills,
        "my_location": sender.location or "",
        "notice_period": sender.notice_period or "",
        "current_ctc": sender.current_ctc or "",
        "expected_ctc": sender.expected_ctc or "",
        "company": job.company,
        "role": job.role,
        "applied_when": when_applied(job.applied_on, today),
        "recipient_first": (recipient_name or "").split()[0]
        if (recipient_name or "").split()
        else "",
        "round_label": "interview",
        "signature": signature(sender),
    }
    for name, value in (overrides or {}).items():
        if name not in OVERRIDABLE or not value.strip():
            continue
        if name == "round":
            values["round_label"] = ROUND_LABELS.get(value.strip().lower(), values["round_label"])
        else:
            values[name] = value.strip()
    return values
