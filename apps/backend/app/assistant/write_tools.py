"""Changes the assistant may propose. None of them happens without a confirmation card.

Each tool has a `preview` (what the card shows, with names resolved so the user sees
"Zepto — Backend Engineer", not an id) and an `execute` that goes through the existing
services, so auto-rules and user scoping are exactly what the app's own forms get.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ConflictError
from app.models.enums import (
    Direction,
    FollowupChannel,
    FollowupStatus,
    InteractionType,
    Source,
    Stage,
    WorkMode,
)
from app.schemas.followup import FollowupCreate, FollowupUpdate
from app.schemas.interaction import InteractionCreate
from app.schemas.opportunity import MoveRequest, OpportunityCreate, OpportunityUpdate
from app.services.followup import FollowupService
from app.services.interaction import InteractionService
from app.services.opportunity import OpportunityService

FieldType = Literal["text", "date", "datetime", "select", "number"]


def field(
    name: str,
    label: str,
    value: object,
    *,
    editable: bool = True,
    type: FieldType = "text",
    options: list[str] | None = None,
) -> dict[str, Any]:
    if isinstance(value, date | datetime):
        value = value.isoformat()
    return {
        "name": name,
        "label": label,
        "value": value,
        "editable": editable,
        "type": type,
        "options": options,
    }


@dataclass(frozen=True)
class ActionPreview:
    title: str
    summary: str
    fields: list[dict[str, Any]]

    def as_json(self) -> dict[str, Any]:
        return {"title": self.title, "summary": self.summary, "fields": self.fields}


@dataclass(frozen=True)
class ActionResult:
    summary: str
    data: dict[str, Any]
    # Query families the client should refetch: opportunities, followups, interactions,
    # dashboard, analytics, contacts.
    changed: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        return {"summary": self.summary, "data": self.data, "changed": list(self.changed)}


@dataclass(frozen=True)
class WriteTool:
    name: str
    description: str
    args: type[BaseModel]
    preview: Callable[[BaseModel], ActionPreview]
    execute: Callable[[BaseModel], ActionResult]

    def as_langchain(self) -> StructuredTool:
        def _never_called(**_: Any) -> str:
            raise RuntimeError("assistant tools are executed by the graph")

        return StructuredTool.from_function(
            func=_never_called, name=self.name, description=self.description, args_schema=self.args
        )


# ---- argument schemas -------------------------------------------------------------------------

STAGES = [s.value for s in Stage]
CHANNELS = [c.value for c in FollowupChannel]
ContactType = Literal["call", "email", "linkedin", "whatsapp", "interview", "nudge"]


class MoveArgs(BaseModel):
    opportunity_id: int
    stage: Stage
    note: str | None = Field(None, max_length=1000, description="Why, if the user said")


class AddFollowupArgs(BaseModel):
    opportunity_id: int
    due_date: date
    channel: FollowupChannel = FollowupChannel.email
    message_draft: str | None = Field(None, max_length=2000)


class MarkFollowupArgs(BaseModel):
    followup_id: int
    status: FollowupStatus = Field(description="done, skipped or pending")


class LogInteractionArgs(BaseModel):
    opportunity_id: int
    type: ContactType
    direction: Direction = Field(Direction.out, description="out = the user reached out")
    summary: str = Field(min_length=1, max_length=2000)
    occurred_at: datetime | None = Field(None, description="Default: now")
    contact_id: int | None = None


class SetNextActionArgs(BaseModel):
    opportunity_id: int
    next_action: str = Field(min_length=1, max_length=500)
    next_action_due: date | None = None


class CreateOpportunityArgs(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    source: Source = Source.other
    stage: Stage = Stage.found
    priority: int = Field(2, ge=1, le=3)
    location: str | None = Field(None, max_length=200)
    work_mode: WorkMode | None = None
    jd_url: str | None = Field(None, max_length=1000)
    stack_tags: list[str] = Field(default_factory=list)
    next_action: str | None = Field(None, max_length=500)


def build_write_tools(
    session: Session, clock: Clock, settings: Settings, user_id: int
) -> dict[str, WriteTool]:
    opportunities = OpportunityService(session, clock, settings, user_id)
    followups = FollowupService(session, clock, user_id)
    interactions = InteractionService(session, clock, user_id)

    def name_of(opportunity_id: int) -> str:
        o = opportunities.get(opportunity_id)  # NotFoundError for another user's id
        return f"{o.company} — {o.role}"

    # -- move ----------------------------------------------------------------------------------
    def move_preview(raw: BaseModel) -> ActionPreview:
        a = MoveArgs.model_validate(raw.model_dump())
        o = opportunities.get(a.opportunity_id)
        if o.stage == a.stage:
            raise ConflictError(f"{o.company} — {o.role} is already in stage '{a.stage.value}'")
        return ActionPreview(
            title=f"Move {o.company} — {o.role}",
            summary=f"{o.stage.value} → {a.stage.value}",
            fields=[
                field("stage", "New stage", a.stage.value, type="select", options=STAGES),
                field("note", "Note", a.note),
            ],
        )

    def move_execute(raw: BaseModel) -> ActionResult:
        a = MoveArgs.model_validate(raw.model_dump())
        before = opportunities.get(a.opportunity_id).stage.value
        moved = opportunities.move(a.opportunity_id, MoveRequest(stage=a.stage, note=a.note))
        o = moved.opportunity
        followup = moved.followup_created
        return ActionResult(
            summary=f"{o.company} — {o.role}: {before} → {o.stage.value}",
            data={
                "opportunity_id": o.id,
                "stage": o.stage.value,
                "followup_created_due": followup.due_date.isoformat() if followup else None,
            },
            changed=("opportunities", "interactions", "followups", "dashboard", "analytics"),
        )

    # -- follow-ups ---------------------------------------------------------------------------
    def add_followup_preview(raw: BaseModel) -> ActionPreview:
        a = AddFollowupArgs.model_validate(raw.model_dump())
        return ActionPreview(
            title=f"Add follow-up for {name_of(a.opportunity_id)}",
            summary=f"{a.channel.value} on {a.due_date:%a %d %b}",
            fields=[
                field("due_date", "Due", a.due_date, type="date"),
                field("channel", "Channel", a.channel.value, type="select", options=CHANNELS),
                field("message_draft", "Draft", a.message_draft),
            ],
        )

    def add_followup_execute(raw: BaseModel) -> ActionResult:
        a = AddFollowupArgs.model_validate(raw.model_dump())
        f = followups.create(FollowupCreate(**a.model_dump()))
        return ActionResult(
            summary=f"Follow-up on {f.due_date:%a %d %b} by {f.channel.value}",
            data={"followup_id": f.id, "due_date": f.due_date.isoformat()},
            changed=("followups", "dashboard"),
        )

    def mark_followup_preview(raw: BaseModel) -> ActionPreview:
        a = MarkFollowupArgs.model_validate(raw.model_dump())
        f = followups.get(a.followup_id)
        verb = {"done": "Mark done", "skipped": "Skip", "pending": "Reopen"}[a.status.value]
        return ActionPreview(
            title=f"{verb}: follow-up for {name_of(f.opportunity_id)}",
            summary=f"due {f.due_date:%a %d %b} ({f.channel.value}) → {a.status.value}",
            fields=[
                field(
                    "status",
                    "Status",
                    a.status.value,
                    type="select",
                    options=[s.value for s in FollowupStatus],
                )
            ],
        )

    def mark_followup_execute(raw: BaseModel) -> ActionResult:
        a = MarkFollowupArgs.model_validate(raw.model_dump())
        f = followups.update(a.followup_id, FollowupUpdate(status=a.status))
        return ActionResult(
            summary=f"Follow-up {f.id} marked {f.status.value}",
            data={"followup_id": f.id, "status": f.status.value},
            changed=("followups", "dashboard"),
        )

    # -- interactions -------------------------------------------------------------------------
    def log_interaction_preview(raw: BaseModel) -> ActionPreview:
        a = LogInteractionArgs.model_validate(raw.model_dump())
        when = (a.occurred_at or clock.now()).astimezone(clock.tz)
        return ActionPreview(
            title=f"Log {a.type} with {name_of(a.opportunity_id)}",
            summary=f"{a.direction.value} · {when:%a %d %b %H:%M}",
            fields=[
                field("summary", "Summary", a.summary),
                field(
                    "type",
                    "Type",
                    a.type,
                    type="select",
                    options=["call", "email", "linkedin", "whatsapp", "interview", "nudge"],
                ),
                field("occurred_at", "When", when, type="datetime"),
            ],
        )

    def log_interaction_execute(raw: BaseModel) -> ActionResult:
        a = LogInteractionArgs.model_validate(raw.model_dump())
        i = interactions.create(
            InteractionCreate(
                opportunity_id=a.opportunity_id,
                contact_id=a.contact_id,
                type=InteractionType(a.type),
                direction=a.direction,
                summary=a.summary,
                occurred_at=a.occurred_at,
            )
        )
        return ActionResult(
            summary=f"Logged {i.type.value} on {i.occurred_at.astimezone(clock.tz):%a %d %b}",
            data={"interaction_id": i.id},
            changed=("interactions", "opportunities", "dashboard"),
        )

    # -- next action --------------------------------------------------------------------------
    def set_next_action_preview(raw: BaseModel) -> ActionPreview:
        a = SetNextActionArgs.model_validate(raw.model_dump())
        due = f" by {a.next_action_due:%a %d %b}" if a.next_action_due else ""
        return ActionPreview(
            title=f"Set next action for {name_of(a.opportunity_id)}",
            summary=f"{a.next_action}{due}",
            fields=[
                field("next_action", "Next action", a.next_action),
                field("next_action_due", "Due", a.next_action_due, type="date"),
            ],
        )

    def set_next_action_execute(raw: BaseModel) -> ActionResult:
        a = SetNextActionArgs.model_validate(raw.model_dump())
        o = opportunities.update(
            a.opportunity_id,
            OpportunityUpdate(next_action=a.next_action, next_action_due=a.next_action_due),
        )
        return ActionResult(
            summary=f"Next action for {o.company} — {o.role} set",
            data={"opportunity_id": o.id},
            changed=("opportunities", "dashboard"),
        )

    # -- create -------------------------------------------------------------------------------
    def create_preview(raw: BaseModel) -> ActionPreview:
        a = CreateOpportunityArgs.model_validate(raw.model_dump())
        return ActionPreview(
            title=f"Add {a.company} — {a.role}",
            summary=f"{a.stage.value} · {a.source.value} · priority {a.priority}",
            fields=[
                field("company", "Company", a.company),
                field("role", "Role", a.role),
                field("stage", "Stage", a.stage.value, type="select", options=STAGES),
                field(
                    "source",
                    "Source",
                    a.source.value,
                    type="select",
                    options=[s.value for s in Source],
                ),
                field("priority", "Priority (1 high – 3 low)", a.priority, type="number"),
                field("location", "Location", a.location),
                field("jd_url", "Job link", a.jd_url),
            ],
        )

    def create_execute(raw: BaseModel) -> ActionResult:
        a = CreateOpportunityArgs.model_validate(raw.model_dump())
        o = opportunities.create(OpportunityCreate(**a.model_dump()))
        return ActionResult(
            summary=f"Added {o.company} — {o.role} ({o.stage.value})",
            data={"opportunity_id": o.id},
            changed=("opportunities", "dashboard", "analytics"),
        )

    tools = [
        WriteTool(
            "move_opportunity",
            "Move an opportunity to another stage (applied, screening, interview_scheduled, "
            "interviewing, offer, accepted, rejected, ghosted, parked). Use list_opportunities "
            "first if you do not know the id.",
            MoveArgs,
            move_preview,
            move_execute,
        ),
        WriteTool(
            "add_followup",
            "Schedule a follow-up for an opportunity on a date.",
            AddFollowupArgs,
            add_followup_preview,
            add_followup_execute,
        ),
        WriteTool(
            "mark_followup",
            "Mark a follow-up done, skipped or pending again.",
            MarkFollowupArgs,
            mark_followup_preview,
            mark_followup_execute,
        ),
        WriteTool(
            "log_interaction",
            "Record a call, email, message, interview or nudge that happened with a company.",
            LogInteractionArgs,
            log_interaction_preview,
            log_interaction_execute,
        ),
        WriteTool(
            "set_next_action",
            "Set or change the next action (and its due date) on an opportunity.",
            SetNextActionArgs,
            set_next_action_preview,
            set_next_action_execute,
        ),
        WriteTool(
            "create_opportunity",
            "Add a new opportunity to the pipeline.",
            CreateOpportunityArgs,
            create_preview,
            create_execute,
        ),
    ]
    return {t.name: t for t in tools}


WRITE_TOOLS = (
    "move_opportunity",
    "add_followup",
    "mark_followup",
    "log_interaction",
    "set_next_action",
    "create_opportunity",
)
