from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ORMModel

WorkModeText = Literal["remote", "hybrid", "onsite"]


class JobSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=200, description="Role, skills or company")
    location: str | None = Field(None, max_length=100)
    work_mode: WorkModeText | None = None
    posted_within_days: int = Field(7, ge=1, le=30)
    limit: int = Field(5, ge=1, le=10)

    @field_validator("query", "location")
    @classmethod
    def _squash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        return value or None


class JobPostingRead(ORMModel):
    id: int
    title: str
    company: str
    location: str | None
    work_mode: str | None
    source_site: str
    provider: str
    apply_url: str
    posted_at: datetime | None
    salary_text: str | None
    active_status: str
    active_checked_at: datetime | None
    description: str | None = None
    # This user's opportunity for the posting, when they already track it.
    tracked_opportunity_id: int | None = None


class Notice(BaseModel):
    code: str
    message: str


class JobSearchResponse(BaseModel):
    results: list[JobPostingRead]
    from_cache: bool
    providers_used: list[str]
    notices: list[Notice]


class TrackJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority: int = Field(2, ge=1, le=3)
    stage: Literal["found", "applied"] = "found"


class ActiveCheckRead(BaseModel):
    id: int
    active_status: str
    active_checked_at: datetime | None
