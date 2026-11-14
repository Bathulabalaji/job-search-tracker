"""The built-in message templates, as data. Versioned in code so every user gets fixes.

Writing rules every template follows (a test enforces the mechanical ones): one clear ask, at
most about 150 words, the recipient's name in the greeting, one specific proof point from the
user's own profile, a plain respectful tone that works in India and abroad. Gaps like
[[something specific you discussed]] are left on purpose where only the user knows the answer.
"""

from dataclasses import dataclass
from typing import Literal

from app.models.enums import ContactRole, Stage

Channel = Literal["email", "linkedin", "linkedin_note"]
Group = Literal["reach_out", "after_applying", "screening", "interviewing", "offer", "closing"]

CATALOG_VERSION = 1
MAX_EMAIL_WORDS = 150
MAX_LINKEDIN_WORDS = 90
LINKEDIN_NOTE_MAX_CHARS = 300  # a connection request note; LinkedIn has changed this before

GROUP_LABELS: dict[str, str] = {
    "reach_out": "Reach out",
    "after_applying": "After applying",
    "screening": "Screening",
    "interviewing": "Interviewing",
    "offer": "Offer",
    "closing": "Closing and staying connected",
}

# Every field a template may use. Computed by messaging/context.py.
KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "recipient_first", "my_name", "my_first_name", "my_email", "headline", "proof_point",
        "bridge", "skills", "my_location", "notice_period", "current_ctc", "expected_ctc",
        "availability", "talking_point", "new_update", "decision_date", "follow_up_detail",
        "company", "role", "applied_when", "round_label", "signature",
    }
)  # fmt: skip


@dataclass(frozen=True)
class Variant:
    channel: Channel
    body: str
    subject: str | None = None  # email only


@dataclass(frozen=True)
class Template:
    key: str
    group: Group
    name: str
    summary: str  # one line: when to send it
    stages: tuple[Stage, ...]
    recipients: tuple[ContactRole, ...]
    variants: tuple[Variant, ...]
    tips: tuple[str, ...] = ()
    india_only: bool = False

    def variant(self, channel: str) -> Variant | None:
        return next((v for v in self.variants if v.channel == channel), None)


R, H, M, F = ContactRole.recruiter, ContactRole.hr, ContactRole.manager, ContactRole.referrer

TEMPLATES: tuple[Template, ...] = (
    Template(
        key="referral_request",
        group="reach_out",
        name="Ask for a referral",
        summary="Someone you know works at the company and the role is open.",
        stages=(Stage.found,),
        recipients=(F,),
        variants=(
            Variant(
                "email",
                subject="Referral request: {{role}} at {{company}}",
                body="""Hi {{recipient_first|there}},

I hope you're doing well. I saw that {{company}} is hiring for {{role}}, and I'd be grateful for a referral if you feel I'm a good fit.

I'm {{my_name}}, {{headline}}.{{?proof_point}} {{proof_point}}{{/}}{{?bridge}} {{bridge}}{{/}}

I'll attach my resume and can send a short note on why I fit the role, so it's easy for you to forward. Thank you for considering it.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, hope you're well. {{company}} is hiring for {{role}}, and I think I'm a strong fit. I'm {{headline}}. Would you be open to referring me? I can send my resume and a short summary so it's quick for you. Thank you! {{my_first_name}}""",
            ),
        ),
        tips=(
            "Ask one person, one thing. A referral request that is easy to forward gets answered.",
            "Attach your best-fit resume as a PDF named YourName_Role.pdf.",
        ),
    ),
    Template(
        key="recruiter_intro",
        group="reach_out",
        name="Introduce yourself to a recruiter",
        summary="You found an open role and want to reach the recruiter or HR directly.",
        stages=(Stage.found,),
        recipients=(R, H),
        variants=(
            Variant(
                "email",
                subject="{{role}} at {{company}}: {{my_name}}",
                body="""Hi {{recipient_first|there}},

I'm {{my_name}}, {{headline}}. I'm interested in the {{role}} role at {{company}} and wanted to reach out directly.

{{?proof_point}}{{proof_point}}{{/}}{{?bridge}} {{bridge}}{{/}}

Would you be open to a quick chat, or could you point me to the right person? I've attached my resume for context.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, I'm interested in the {{role}} role at {{company}}. I'm {{headline}}. Could I share my resume, or would a quick chat be possible? Thanks, {{my_first_name}}""",
            ),
        ),
        tips=("Send Tuesday to Thursday morning, in the recipient's time zone.",),
    ),
    Template(
        key="connect_note",
        group="reach_out",
        name="LinkedIn connection note",
        summary="A short note to attach when you send a connection request.",
        stages=(Stage.found,),
        recipients=(R, H, M, F),
        variants=(
            Variant(
                "linkedin_note",
                body="""Hi {{recipient_first|there}}, I'm {{headline}} and I'm exploring {{role}} roles at {{company}}. I'd love to connect and learn more about the team. Thanks, {{my_first_name}}""",
            ),
        ),
        tips=(
            "LinkedIn limits this note to about 300 characters, so every word has to earn its place.",
        ),
    ),
    Template(
        key="applied_intro",
        group="after_applying",
        name="I've applied: a quick introduction",
        summary="Right after you apply, so a person sees your name next to the application.",
        stages=(Stage.applied,),
        recipients=(R, H, F),
        variants=(
            Variant(
                "email",
                subject="Applied: {{role}}, {{my_name}}",
                body="""Hi {{recipient_first|there}},

I applied {{applied_when}} for the {{role}} position at {{company}} and wanted to introduce myself directly.

I'm {{my_name}}, {{headline}}.{{?proof_point}} {{proof_point}}{{/}}{{?skills}} My core stack is {{skills}}.{{/}}

I'd be glad to share anything else that helps. Thank you for your time.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, I applied {{applied_when}} for the {{role}} role at {{company}} and wanted to say hello. I'm {{headline}}. Happy to share anything that helps. Thanks, {{my_first_name}}""",
            ),
        ),
    ),
    Template(
        key="follow_up_1",
        group="after_applying",
        name="Follow-up 1: checking in",
        summary="About 5 working days after applying with no reply.",
        stages=(Stage.applied,),
        recipients=(R, H),
        variants=(
            Variant(
                "email",
                subject="Following up: {{role}} application, {{my_name}}",
                body="""Hi {{recipient_first|there}},

I applied for the {{role}} role at {{company}} {{applied_when}} and wanted to check in on the status of my application.

{{?proof_point}}A quick reminder of what I'd bring: {{proof_point}}{{/}}

If there's anything more I can share, I'm happy to. Thank you for your time.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, I applied for the {{role}} role at {{company}} {{applied_when}} and wanted to check on the status. Happy to share anything more that helps. Thanks, {{my_first_name}}""",
            ),
        ),
        tips=("Keep it short and polite. One question: where does my application stand?",),
    ),
    Template(
        key="follow_up_2",
        group="after_applying",
        name="Follow-up 2: with something new",
        summary="About 7 working days after the first follow-up.",
        stages=(Stage.applied,),
        recipients=(R, H),
        variants=(
            Variant(
                "email",
                subject="Following up again: {{role}}, {{my_name}}",
                body="""Hi {{recipient_first|there}},

I'm following up once more on my application for {{role}} at {{company}}. Since I last wrote, {{new_update}}.

I remain very interested and would welcome a short conversation whenever it suits you.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, following up on my {{role}} application at {{company}}. Since I last wrote, {{new_update}}. I'd still love to talk if there's a fit. Thanks, {{my_first_name}}""",
            ),
        ),
        tips=(
            "A second nudge works when it adds something: a project, a result, a certification.",
        ),
    ),
    Template(
        key="follow_up_final",
        group="after_applying",
        name="Closing the loop",
        summary="The last nudge, about 7 working days after follow-up 2.",
        stages=(Stage.applied,),
        recipients=(R, H),
        variants=(
            Variant(
                "email",
                subject="Closing the loop: {{role}}, {{my_name}}",
                body="""Hi {{recipient_first|there}},

I wanted to close the loop on my application for {{role}} at {{company}}. If the role has been filled or the team is moving in another direction, I completely understand, and a quick note either way would help me plan.

If it makes sense later, I'd be glad to stay in touch about future openings.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, closing the loop on my {{role}} application at {{company}}. If the role is filled, no problem, and I'd welcome staying in touch for future openings. Thanks, {{my_first_name}}""",
            ),
        ),
        tips=("Three unanswered messages is the limit. After this, move on and mark it ghosted.",),
    ),
    Template(
        key="thank_you_screening",
        group="screening",
        name="Thank you after a recruiter call",
        summary="Within 24 hours of a screening or recruiter conversation.",
        stages=(Stage.screening,),
        recipients=(R, H),
        variants=(
            Variant(
                "email",
                subject="Thank you: {{role}} at {{company}}",
                body="""Hi {{recipient_first|there}},

Thank you for taking the time to speak with me about the {{role}} role at {{company}}. I enjoyed learning about {{talking_point}}, and it strengthened my interest in the position.

Please let me know if you need anything further from me.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, thank you for the call about the {{role}} role at {{company}}. I enjoyed learning about {{talking_point}}. Please tell me if you need anything from me. {{my_first_name}}""",
            ),
        ),
    ),
    Template(
        key="share_details",
        group="screening",
        name="Share notice period and CTC details",
        summary="A recruiter asked for your current and expected CTC, notice period and availability.",
        stages=(Stage.screening, Stage.interview_scheduled),
        recipients=(R, H),
        india_only=True,
        variants=(
            Variant(
                "email",
                subject="Re: {{role}} at {{company}}: my details",
                body="""Hi {{recipient_first|there}},

Thank you for reaching out. Here are the details you asked for:

- Current location: {{my_location}}
- Notice period: {{notice_period}}
- Current CTC: {{current_ctc}}
- Expected CTC: {{expected_ctc}}
- Available for a call: {{availability}}

Please let me know if you need anything else.

{{signature}}""",
            ),
        ),
        tips=("Answer exactly what was asked, in the order it was asked.",),
    ),
    Template(
        key="thank_you_interview",
        group="interviewing",
        name="Thank you after an interview",
        summary="Within 24 hours of any interview round.",
        stages=(Stage.interviewing, Stage.interview_scheduled),
        recipients=(M, R, H),
        variants=(
            Variant(
                "email",
                subject="Thank you: {{round_label}} for {{role}}",
                body="""Hi {{recipient_first|there}},

Thank you for the {{round_label}}. I enjoyed our discussion about {{talking_point}} and came away even more excited about the {{role}} role at {{company}}.

{{?follow_up_detail}}{{follow_up_detail}} {{/}}I'm happy to answer any further questions.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, thank you for the {{round_label}} today. I enjoyed our discussion about {{talking_point}} and I'm even more excited about the {{role}} role at {{company}}. {{my_first_name}}""",
            ),
        ),
        tips=("Mention one specific thing from the conversation. Generic thanks are ignored.",),
    ),
    Template(
        key="interview_follow_up",
        group="interviewing",
        name="No decision yet: checking in",
        summary="About 5 working days after an interview with no update.",
        stages=(Stage.interviewing,),
        recipients=(R, M, H),
        variants=(
            Variant(
                "email",
                subject="Checking in: {{role}}, {{my_name}}",
                body="""Hi {{recipient_first|there}},

I hope you're well. I wanted to follow up on the {{role}} interview process at {{company}}. I remain very interested, and I'd appreciate any update on next steps or timing.

Thank you again for your time.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, hope you're well. Checking in on the {{role}} process at {{company}}. I'm still very interested and would appreciate any update on next steps. Thanks, {{my_first_name}}""",
            ),
        ),
    ),
    Template(
        key="acknowledge_offer",
        group="offer",
        name="Acknowledge the offer and ask for time",
        summary="Within 24 hours of receiving an offer.",
        stages=(Stage.offer,),
        recipients=(R, H),
        variants=(
            Variant(
                "email",
                subject="Re: Offer for {{role}} at {{company}}",
                body="""Hi {{recipient_first|there}},

Thank you very much for the offer for the {{role}} position at {{company}}. I'm excited about the opportunity.

I'd like to review the details carefully. Could I confirm my decision by {{decision_date}}? Meanwhile, please let me know if you need anything from me.

{{signature}}""",
            ),
        ),
        tips=("Always reply within a day, even if you need time to decide.",),
    ),
    Template(
        key="negotiate_offer",
        group="offer",
        name="Discuss the compensation",
        summary="You want to negotiate, politely and with a reason.",
        stages=(Stage.offer,),
        recipients=(R, H),
        variants=(
            Variant(
                "email",
                subject="Re: Offer for {{role}} at {{company}}: compensation",
                body="""Hi {{recipient_first|there}},

Thank you again for the offer. I'm enthusiastic about joining {{company}} as {{role}}.

Based on my experience and the scope of the role, I was hoping we could discuss the compensation. I was looking for {{expected_ctc}}. Is there flexibility to move closer to that?

I'm keen to find something that works for both of us and to get started.

{{signature}}""",
            ),
        ),
        tips=(
            "Say what you'd like, then ask a question. Don't give an ultimatum.",
            "Know your market range before you send this.",
        ),
    ),
    Template(
        key="reply_to_rejection",
        group="closing",
        name="Reply gracefully to a rejection",
        summary="You were turned down. Keep the relationship and ask for feedback.",
        stages=(Stage.rejected,),
        recipients=(R, M, H),
        variants=(
            Variant(
                "email",
                subject="Thank you: {{role}} at {{company}}",
                body="""Hi {{recipient_first|there}},

Thank you for letting me know, and for the time you and the team spent with me on the {{role}} role.

If you're able to share any feedback on how I could strengthen my application, I'd be very grateful. I'd also welcome staying in touch about future openings at {{company}}.

{{signature}}""",
            ),
            Variant(
                "linkedin",
                body="""Hi {{recipient_first|there}}, thank you for letting me know about the {{role}} role at {{company}}. If you have any feedback, I'd be grateful, and I'd love to stay in touch for future openings. {{my_first_name}}""",
            ),
        ),
    ),
)

BY_KEY: dict[str, Template] = {t.key: t for t in TEMPLATES}
FOLLOW_UP_CHAIN = ("applied_intro", "follow_up_1", "follow_up_2", "follow_up_final")


def get(key: str) -> Template | None:
    return BY_KEY.get(key)
