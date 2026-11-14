"""What should this person send next, and why? Pure rules, no database.

The cadence follows what recruiters tolerate: a nudge about 5 working days after applying, a
second one a week later with something new, a last one a week after that, then stop. A thank-you
within a few days of any call or interview. Nobody is messaged twice within 3 days.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from app.messaging.catalog import BY_KEY, FOLLOW_UP_CHAIN, Channel
from app.models.enums import ContactRole, Stage
from app.services import rules

Kind = Literal["send", "wait", "stop", "add_contact"]
FOLLOW_UPS = FOLLOW_UP_CHAIN[1:]  # the nudges, after the introduction


@dataclass(frozen=True)
class ContactInfo:
    id: int
    name: str
    role: ContactRole
    email: str | None
    linkedin_url: str | None
    last_messaged_on: date | None = None


@dataclass(frozen=True)
class SentInfo:
    template_key: str
    sent_on: date


@dataclass
class Situation:
    stage: Stage
    today: date
    applied_on: date | None
    sent: list[SentInfo] = field(default_factory=list)
    last_outbound_on: date | None = None  # any message or logged outbound contact
    last_inbound_on: date | None = None  # they wrote or called
    last_conversation_on: date | None = None  # a call or interview took place
    contacts: list[ContactInfo] = field(default_factory=list)
    india_style: bool = True


@dataclass(frozen=True)
class Suggestion:
    kind: Kind
    title: str
    reason: str
    template_key: str | None = None
    channel: Channel | None = None
    contact_id: int | None = None
    due: bool = False


def _sent_keys(s: Situation) -> set[str]:
    return {m.template_key for m in s.sent}


def _sent_after(s: Situation, key: str, moment: date | None) -> bool:
    return any(m.template_key == key and (moment is None or m.sent_on >= moment) for m in s.sent)


def _contact_for(roles: tuple[ContactRole, ...], contacts: list[ContactInfo]) -> ContactInfo | None:
    for role in roles:
        match = next((c for c in contacts if c.role == role), None)
        if match is not None:
            return match
    return contacts[0] if contacts else None


def _channel(contact: ContactInfo | None, wanted: Channel) -> Channel:
    if wanted == "linkedin_note":
        return wanted
    if contact is None:
        return wanted
    if wanted == "email" and contact.email:
        return "email"
    if contact.linkedin_url and not (wanted == "email" and contact.email):
        return "linkedin"
    return wanted


def _send(
    s: Situation,
    key: str,
    reason: str,
    *,
    due: bool,
    prefer: Channel = "email",
) -> Suggestion:
    template = BY_KEY[key]
    contact = _contact_for(template.recipients, s.contacts)
    channel = _channel(contact, prefer)
    if contact is not None and contact.last_messaged_on is not None and due:
        gap = (s.today - contact.last_messaged_on).days
        if gap < rules.CONTACT_COOLDOWN_DAYS:
            wait_until = contact.last_messaged_on + timedelta(days=rules.CONTACT_COOLDOWN_DAYS)
            return Suggestion(
                "wait",
                template.name,
                f"You messaged {contact.name} {'today' if gap == 0 else f'{gap} day(s) ago'}. "
                f"Give it until {wait_until.day} {wait_until:%b} before the next one.",
                key,
                channel,
                contact.id,
                due=False,
            )
    return Suggestion(
        "send", template.name, reason, key, channel, contact.id if contact else None, due=due
    )


def _wait(title: str, working_days_left: int, key: str | None = None) -> Suggestion:
    plural = "s" if working_days_left != 1 else ""
    return Suggestion(
        "wait",
        title,
        f"Not yet. This is due in {working_days_left} working day{plural}.",
        key,
        due=False,
    )


def _applied_chain(s: Situation) -> list[Suggestion]:
    """Introduction, then up to three nudges, then stop."""
    if s.last_inbound_on and (
        s.last_outbound_on is None or s.last_inbound_on >= s.last_outbound_on
    ):
        return []  # they answered: the next move is a conversation, not a nudge
    keys = _sent_keys(s)
    nudges_sent = sum(1 for k in FOLLOW_UPS if k in keys)
    out: list[Suggestion] = []
    if "applied_intro" not in keys and nudges_sent == 0:
        recent = s.applied_on is not None and (s.today - s.applied_on).days <= 3
        if recent:
            out.append(
                _send(
                    s,
                    "applied_intro",
                    "You applied recently. Put your name in front of a person.",
                    due=True,
                )
            )
    if nudges_sent >= len(FOLLOW_UPS):
        return [
            Suggestion(
                "stop",
                "Move on",
                "Three messages and no reply. Stop here and mark it ghosted, so the "
                "search can focus on live opportunities.",
            ),
            *out,
        ]
    key = FOLLOW_UPS[nudges_sent]
    base = max([d for d in (s.applied_on, s.last_outbound_on) if d is not None], default=None)
    if base is None:
        return out
    needed = rules.FIRST_FOLLOW_UP_AFTER if nudges_sent == 0 else rules.NEXT_FOLLOW_UP_AFTER
    elapsed = rules.working_days_between(base, s.today)
    why = {
        "follow_up_1": f"{elapsed} working days since you applied with no reply.",
        "follow_up_2": f"{elapsed} working days since your last message. Add something new.",
        "follow_up_final": f"{elapsed} working days since your last message. A closing note.",
    }[key]
    if elapsed >= needed:
        out.append(_send(s, key, why, due=True))
    else:
        out.append(_wait(BY_KEY[key].name, needed - elapsed, key))
    return out


def suggest(s: Situation) -> list[Suggestion]:
    out: list[Suggestion] = []
    keys = _sent_keys(s)
    if s.stage == Stage.found:
        if not s.contacts:
            return [
                Suggestion(
                    "add_contact",
                    "Add someone to write to",
                    "Add the recruiter, HR or a referrer to this opportunity, then message them.",
                )
            ]
        roles = {c.role for c in s.contacts}
        if ContactRole.referrer in roles and "referral_request" not in keys:
            out.append(
                _send(
                    s,
                    "referral_request",
                    "A referral beats a cold application. Ask first.",
                    due=True,
                )
            )
        if roles & {ContactRole.recruiter, ContactRole.hr} and "recruiter_intro" not in keys:
            out.append(
                _send(
                    s,
                    "recruiter_intro",
                    "Reach the recruiter directly before you apply.",
                    due=not out,
                )
            )
        if "connect_note" not in keys and any(c.linkedin_url for c in s.contacts):
            out.append(
                _send(
                    s,
                    "connect_note",
                    "Connect on LinkedIn with a short note.",
                    due=not out,
                    prefer="linkedin_note",
                )
            )
    elif s.stage == Stage.applied:
        out = _applied_chain(s)
    elif s.stage == Stage.screening:
        since_call = s.last_conversation_on
        if (
            since_call is not None
            and (s.today - since_call).days <= rules.THANK_YOU_WINDOW_DAYS
            and not _sent_after(s, "thank_you_screening", since_call)
        ):
            out.append(
                _send(
                    s,
                    "thank_you_screening",
                    "You spoke recently. Thank them within a day.",
                    due=True,
                )
            )
        if s.india_style:
            out.append(
                _send(
                    s,
                    "share_details",
                    "Use this when a recruiter asks for your notice period and CTC.",
                    due=False,
                )
            )
        if not out or all(not o.due for o in out):
            out = [*_applied_chain(s), *out]
    elif s.stage == Stage.interview_scheduled:
        if s.india_style:
            out.append(
                _send(
                    s,
                    "share_details",
                    "Use this when a recruiter asks for your notice period and CTC.",
                    due=False,
                )
            )
    elif s.stage == Stage.interviewing:
        held = s.last_conversation_on
        if (
            held is not None
            and (s.today - held).days <= rules.THANK_YOU_WINDOW_DAYS
            and not _sent_after(s, "thank_you_interview", held)
        ):
            out.append(
                _send(
                    s,
                    "thank_you_interview",
                    "Thank them within 24 hours of the interview.",
                    due=True,
                )
            )
        elif s.last_inbound_on is None or (held and s.last_inbound_on < held):
            base = held or s.last_outbound_on
            if base is not None:
                elapsed = rules.working_days_between(base, s.today)
                if elapsed >= rules.INTERVIEW_NUDGE_AFTER:
                    out.append(
                        _send(
                            s,
                            "interview_follow_up",
                            f"{elapsed} working days since the interview with no update.",
                            due=True,
                        )
                    )
                else:
                    out.append(
                        _wait(
                            BY_KEY["interview_follow_up"].name,
                            rules.INTERVIEW_NUDGE_AFTER - elapsed,
                            "interview_follow_up",
                        )
                    )
    elif s.stage == Stage.offer:
        if "acknowledge_offer" not in keys:
            out.append(
                _send(
                    s,
                    "acknowledge_offer",
                    "Reply within a day, even if you need time to decide.",
                    due=True,
                )
            )
        if "negotiate_offer" not in keys:
            out.append(
                _send(
                    s,
                    "negotiate_offer",
                    "If you want to discuss the compensation, do it politely and with a reason.",
                    due=False,
                )
            )
    elif s.stage == Stage.rejected:
        if "reply_to_rejection" not in keys:
            out.append(
                _send(
                    s, "reply_to_rejection", "Keep the relationship and ask for feedback.", due=True
                )
            )
    order = {"send": 0, "stop": 1, "wait": 2, "add_contact": 3}
    return sorted(out, key=lambda x: (not x.due, order[x.kind]))
