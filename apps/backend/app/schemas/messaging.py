import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContactRole, Stage
from app.schemas.common import ORMModel, PatchModel
from app.schemas.text import CleanText, EmailAddress, HttpLink, OneLine

Channel = Literal["email", "linkedin", "linkedin_note"]
SentChannel = Literal["email", "linkedin"]
MAX_BODY = 3000
MAX_SUBJECT = 200


# ---- the sender -------------------------------------------------------------------------------


class OutreachProfileRead(ORMModel):
    from_email: str  # the stored address, or the account email when none was saved
    headline: str | None
    phone: str | None
    linkedin_url: str | None
    location: str | None
    notice_period: str | None
    current_ctc: str | None
    expected_ctc: str | None
    career_story: str | None
    proof_points: list[str]
    india_style: bool
    suggested_headline: str | None = None  # built from the user's resumes, to offer as a start


class OutreachProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_email: EmailAddress | None = Field(None, max_length=254)
    headline: OneLine | None = Field(None, max_length=300)
    phone: OneLine | None = Field(None, max_length=50)
    linkedin_url: HttpLink | None = Field(None, max_length=500)
    location: OneLine | None = Field(None, max_length=200)
    notice_period: OneLine | None = Field(None, max_length=100)
    current_ctc: OneLine | None = Field(None, max_length=100)
    expected_ctc: OneLine | None = Field(None, max_length=100)
    career_story: OneLine | None = Field(None, max_length=500)
    proof_points: list[OneLine] | None = Field(None, max_length=3)
    india_style: bool | None = None


# ---- templates --------------------------------------------------------------------------------


class VariantRead(BaseModel):
    channel: Channel
    subject: str | None
    body: str
    edited: bool = False  # the user's own version of a built-in
    template_id: int | None = None  # the user's row, when there is one


class TemplateRead(BaseModel):
    key: str  # "sys:follow_up_1" or "usr:12"
    source: Literal["system", "custom"]
    group: str
    group_label: str
    name: str
    summary: str
    stages: list[Stage]
    recipients: list[ContactRole]
    india_only: bool
    tips: list[str]
    variants: list[VariantRead]
    archived: bool = False


class TemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: OneLine = Field(min_length=1, max_length=120)
    channel: Channel
    subject: OneLine | None = Field(None, max_length=MAX_SUBJECT)
    body: CleanText = Field(min_length=1, max_length=MAX_BODY)
    stages: list[Stage] = Field(default_factory=list, max_length=10)
    recipient_roles: list[ContactRole] = Field(default_factory=list, max_length=4)
    base_key: str | None = Field(None, max_length=60)  # make an editable copy of a built-in


class TemplateUpdate(PatchModel):
    non_nullable = frozenset({"name", "body", "archived"})
    model_config = ConfigDict(extra="forbid")

    name: OneLine | None = Field(None, min_length=1, max_length=120)
    subject: OneLine | None = Field(None, max_length=MAX_SUBJECT)
    body: CleanText | None = Field(None, min_length=1, max_length=MAX_BODY)
    stages: list[Stage] | None = Field(None, max_length=10)
    recipient_roles: list[ContactRole] | None = Field(None, max_length=4)
    archived: bool | None = None


# ---- drafting ---------------------------------------------------------------------------------


class ContactChoice(BaseModel):
    id: int
    name: str
    role: ContactRole
    email: str | None
    linkedin_url: str | None
    last_messaged_days: int | None  # days since the user last messaged this person


class SuggestionRead(BaseModel):
    kind: Literal["send", "wait", "stop", "add_contact"]
    template_key: str | None
    channel: Channel | None
    contact_id: int | None
    title: str
    reason: str
    due: bool  # true: send it now; false: shown as upcoming


class SuggestionsRead(BaseModel):
    suggestions: list[SuggestionRead]
    contacts: list[ContactChoice]


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_key: str = Field(max_length=80)
    channel: Channel
    contact_id: int | None = None
    # Values the user filled in for gaps (talking_point, new_update, availability, ...).
    fields: dict[str, OneLine] = Field(default_factory=dict, max_length=20)


class MissingField(BaseModel):
    name: str
    label: str


class AttachHint(BaseModel):
    resume_id: int
    label: str
    score: int | None  # the stored match score for this job, when one exists
    has_file: bool


class PreviewRead(BaseModel):
    template_key: str
    template_name: str
    channel: Channel
    to: str | None  # the recipient's email, or LinkedIn link
    to_name: str | None
    from_email: str
    subject: str | None
    body: str
    missing: list[MissingField]
    char_count: int
    char_limit: int | None
    warnings: list[str]
    tips: list[str]
    attach: AttachHint | None
    edited: bool  # rendered from the user's own version of a built-in


class PolishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: OneLine | None = Field(None, max_length=MAX_SUBJECT)
    body: CleanText = Field(min_length=1, max_length=MAX_BODY)
    instruction: Literal["shorter", "warmer", "more_formal", "more_direct", "fix_grammar"]


class PolishRead(BaseModel):
    subject: str | None
    body: str
    changed: bool
    notice: str | None = None  # why the original came back unchanged


class MarkSentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_key: str = Field(max_length=80)
    channel: SentChannel
    contact_id: int | None = None
    subject: OneLine | None = Field(None, max_length=MAX_SUBJECT)
    body: CleanText = Field(min_length=1, max_length=MAX_BODY)
    schedule_next: bool = True
    request_id: uuid.UUID | None = None  # a retry with the same id changes nothing


class OutreachMessageRead(ORMModel):
    id: int
    opportunity_id: int
    contact_id: int | None
    template_key: str
    channel: str
    subject: str | None
    body: str
    sent_at: datetime
    replied_at: datetime | None


class SentRead(BaseModel):
    message: OutreachMessageRead
    followup_closed_id: int | None
    next_followup_id: int | None
    next_followup_due: str | None
    already_recorded: bool = False


class SentListItem(OutreachMessageRead):
    template_name: str | None = None


class StatRow(BaseModel):
    key: str
    name: str
    channel: str
    sent: int
    replied: int
    reply_rate: float  # replied / sent, 0-1


class StatsRead(BaseModel):
    sent: int
    replied: int
    reply_rate: float
    by_template: list[StatRow]
