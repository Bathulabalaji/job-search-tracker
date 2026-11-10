from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.enums import Source, Stage, WorkMode
from app.schemas.common import ORMModel, PatchModel
from app.schemas.followup import FollowupRead
from app.schemas.interaction import InteractionRead

Priority = Annotated[int, Field(ge=1, le=3)]
FitScore = Annotated[int, Field(ge=0, le=100)]


class OpportunityCreate(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    source: Source = Source.other
    stack_tags: list[Annotated[str, Field(min_length=1, max_length=50)]] = []
    location: str | None = Field(default=None, max_length=200)
    work_mode: WorkMode | None = None
    stage: Stage = Stage.found
    priority: Priority = 2
    fit_score: FitScore | None = None
    jd_text: str | None = None
    jd_url: str | None = Field(default=None, max_length=1000)
    expected_ctc_note: str | None = Field(default=None, max_length=500)
    next_action: str | None = Field(default=None, max_length=500)
    next_action_due: date | None = None


class OpportunityUpdate(PatchModel):
    """Stage is intentionally absent: change it with POST /opportunities/{id}/move."""

    non_nullable = frozenset({"company", "role", "source", "stack_tags", "priority"})

    company: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=200)
    source: Source | None = None
    stack_tags: list[Annotated[str, Field(min_length=1, max_length=50)]] | None = None
    location: str | None = Field(default=None, max_length=200)
    work_mode: WorkMode | None = None
    priority: Priority | None = None
    fit_score: FitScore | None = None
    jd_text: str | None = None
    jd_url: str | None = Field(default=None, max_length=1000)
    expected_ctc_note: str | None = Field(default=None, max_length=500)
    next_action: str | None = Field(default=None, max_length=500)
    next_action_due: date | None = None


class OpportunityRead(ORMModel):
    id: int
    company: str
    role: str
    source: Source
    stack_tags: list[str]
    location: str | None
    work_mode: WorkMode | None
    stage: Stage
    priority: int
    fit_score: int | None
    jd_text: str | None
    jd_url: str | None
    expected_ctc_note: str | None
    next_action: str | None
    next_action_due: date | None
    created_at: datetime
    updated_at: datetime
    # Derived by the service, not stored.
    last_contact_at: datetime | None = None
    days_since_contact: int = 0
    ghosted_suggestion: bool = False


class MoveRequest(BaseModel):
    stage: Stage
    note: str | None = Field(default=None, max_length=1000)


class MoveResponse(BaseModel):
    opportunity: OpportunityRead
    interaction: InteractionRead
    followup_created: FollowupRead | None
