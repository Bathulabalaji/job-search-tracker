from datetime import date, timedelta

from app.messaging.context import JobFacts, Sender, build_values, suggest_headline, when_applied
from app.messaging.render import render
from app.messaging.suggest import ContactInfo, SentInfo, Situation, suggest
from app.models.enums import ContactRole, Stage

TODAY = date(2026, 11, 17)  # a Tuesday


def sender(**kw: object) -> Sender:
    return Sender(name="Balaji Bathula", account_email="acct@example.com", **kw)  # type: ignore[arg-type]


def test_the_from_address_is_used_when_given_else_the_account_email() -> None:
    job = JobFacts("Zepto", "Backend Engineer")
    a = build_values(sender=sender(), job=job, recipient_name=None, today=TODAY)
    b = build_values(
        sender=sender(from_email="me@work.example"), job=job, recipient_name=None, today=TODAY
    )
    assert a["my_email"] == "acct@example.com" and "acct@example.com" in a["signature"]
    assert b["my_email"] == "me@work.example" and "me@work.example" in b["signature"]


def test_signature_skips_what_is_missing() -> None:
    values = build_values(
        sender=sender(phone="+91 98765 43210", linkedin_url="https://linkedin.com/in/b"),
        job=JobFacts("Z", "R"), recipient_name="Riya Sharma", today=TODAY,
    )  # fmt: skip
    assert values["signature"].splitlines() == [
        "Thanks and regards,",
        "Balaji Bathula",
        "acct@example.com | +91 98765 43210",
        "https://linkedin.com/in/b",
    ]
    assert values["recipient_first"] == "Riya" and values["my_first_name"] == "Balaji"


def test_applied_wording_and_skills() -> None:
    assert when_applied(None, TODAY) == "recently"
    assert when_applied(TODAY, TODAY) == "today"
    assert when_applied(TODAY - timedelta(days=1), TODAY) == "yesterday"
    assert when_applied(date(2026, 11, 10), TODAY) == "on 10 Nov"
    job = JobFacts("Z", "R", stack_tags=["python", "fastapi", "postgres", "aws"])
    assert build_values(sender=sender(), job=job, recipient_name=None, today=TODAY)["skills"] == (
        "python, fastapi and postgres"
    )


def test_filled_in_gaps_win_and_unknown_fields_are_ignored() -> None:
    values = build_values(
        sender=sender(), job=JobFacts("Z", "R"), recipient_name=None, today=TODAY,
        overrides={"talking_point": "the payments roadmap", "round": "technical", "company": "X"},
    )  # fmt: skip
    assert values["talking_point"] == "the payments roadmap"
    assert values["round_label"] == "technical interview" and values["company"] == "Z"


def test_a_data_value_cannot_break_out_of_a_draft() -> None:
    values = build_values(
        sender=sender(headline="a dev {{company}}"), job=JobFacts("Z{{x}}", "R"),
        recipient_name="{{signature}} Rao", today=TODAY,
    )  # fmt: skip
    text = render("{{recipient_first}} / {{headline}} / {{company}}", values).text
    assert "{{" not in text


def test_headline_is_built_from_the_resume() -> None:
    assert (
        suggest_headline(["Senior Software Engineer"], 4)
        == "a senior Software Engineer with 4 years of experience"
    )
    assert suggest_headline(["Android developer"], None) == "an android developer"
    assert suggest_headline([], 3) is None


# ---- cadence ----------------------------------------------------------------------------------

RECRUITER = ContactInfo(
    1, "Riya", ContactRole.recruiter, "riya@z.example", "https://linkedin.com/in/r"
)


def situation(stage: Stage, **kw: object) -> Situation:
    base: dict[str, object] = {
        "stage": stage,
        "today": TODAY,
        "applied_on": None,
        "contacts": [RECRUITER],
    }
    base.update(kw)
    return Situation(**base)  # type: ignore[arg-type]


def keys(s: Situation) -> list[tuple[str, str | None, bool]]:
    return [(x.kind, x.template_key, x.due) for x in suggest(s)]


def test_found_asks_for_a_contact_when_there_is_none() -> None:
    [s] = suggest(situation(Stage.found, contacts=[]))
    assert s.kind == "add_contact"


def test_found_prefers_a_referrer_then_the_recruiter() -> None:
    referrer = ContactInfo(2, "Amit", ContactRole.referrer, "a@x.example", None)
    out = keys(situation(Stage.found, contacts=[RECRUITER, referrer]))
    assert out[0] == ("send", "referral_request", True)
    assert ("send", "recruiter_intro", False) in out


def test_first_follow_up_waits_five_working_days() -> None:
    applied = TODAY - timedelta(days=3)  # Saturday: only 2 working days have passed
    [s] = [
        x
        for x in suggest(situation(Stage.applied, applied_on=applied))
        if x.template_key == "follow_up_1"
    ]
    assert s.kind == "wait" and "working day" in s.reason
    due = situation(Stage.applied, applied_on=TODAY - timedelta(days=8))  # 6 working days
    assert ("send", "follow_up_1", True) in keys(due)


def test_applied_just_now_suggests_the_introduction() -> None:
    assert keys(situation(Stage.applied, applied_on=TODAY))[0] == ("send", "applied_intro", True)


def test_the_chain_advances_and_then_stops() -> None:
    long_ago = TODAY - timedelta(days=30)
    sent = [SentInfo("follow_up_1", TODAY - timedelta(days=20))]
    s2 = situation(
        Stage.applied, applied_on=long_ago, sent=sent, last_outbound_on=TODAY - timedelta(days=20)
    )
    assert ("send", "follow_up_2", True) in keys(s2)
    sent3 = [*sent, SentInfo("follow_up_2", TODAY - timedelta(days=12))]
    s3 = situation(
        Stage.applied, applied_on=long_ago, sent=sent3, last_outbound_on=TODAY - timedelta(days=12)
    )
    assert ("send", "follow_up_final", True) in keys(s3)
    sent4 = [*sent3, SentInfo("follow_up_final", TODAY - timedelta(days=5))]
    s4 = situation(
        Stage.applied, applied_on=long_ago, sent=sent4, last_outbound_on=TODAY - timedelta(days=5)
    )
    assert [k for k, _, _ in keys(s4)][0] == "stop"


def test_a_reply_ends_the_nudging() -> None:
    s = situation(
        Stage.applied, applied_on=TODAY - timedelta(days=20),
        last_outbound_on=TODAY - timedelta(days=10), last_inbound_on=TODAY - timedelta(days=2),
    )  # fmt: skip
    assert suggest(s) == []


def test_nobody_is_messaged_twice_within_three_days() -> None:
    recent = ContactInfo(
        1, "Riya", ContactRole.recruiter, "riya@z.example", None, TODAY - timedelta(days=1)
    )
    s = situation(Stage.applied, applied_on=TODAY - timedelta(days=12), contacts=[recent])
    [x] = [y for y in suggest(s) if y.template_key == "follow_up_1"]
    assert x.kind == "wait" and "Riya" in x.reason and not x.due


def test_thank_you_after_an_interview_then_a_nudge() -> None:
    held = TODAY - timedelta(days=1)
    assert keys(situation(Stage.interviewing, last_conversation_on=held))[0] == (
        "send",
        "thank_you_interview",
        True,
    )
    thanked = situation(
        Stage.interviewing, last_conversation_on=TODAY - timedelta(days=10),
        sent=[SentInfo("thank_you_interview", TODAY - timedelta(days=9))],
    )  # fmt: skip
    assert ("send", "interview_follow_up", True) in keys(thanked)


def test_offer_and_rejection() -> None:
    assert keys(situation(Stage.offer))[0] == ("send", "acknowledge_offer", True)
    done = situation(Stage.offer, sent=[SentInfo("acknowledge_offer", TODAY)])
    assert keys(done) == [("send", "negotiate_offer", False)]
    assert keys(situation(Stage.rejected))[0] == ("send", "reply_to_rejection", True)
    assert suggest(situation(Stage.accepted)) == []


def test_channel_follows_what_the_contact_has() -> None:
    only_li = ContactInfo(3, "Sam", ContactRole.recruiter, None, "https://linkedin.com/in/s")
    [x] = [
        y
        for y in suggest(
            situation(Stage.applied, applied_on=TODAY - timedelta(days=9), contacts=[only_li])
        )
    ]
    assert x.channel == "linkedin"
    assert (
        suggest(situation(Stage.applied, applied_on=TODAY - timedelta(days=9)))[0].channel
        == "email"
    )
