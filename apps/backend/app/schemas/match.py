from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.job import JobPostingRead, Notice, WorkModeText


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resume_ids: list[int] | None = Field(None, max_length=10)
    force: bool = False  # recompute even when nothing changed


class ResumeMatch(BaseModel):
    resume_id: int
    label: str
    # Mean cosine similarity of the resume's best passages to the JD (None: not indexed yet).
    vector_score: float | None
    score: int | None  # 0-100 from the model's rubric
    matched_skills: list[str]
    missing_skills: list[str]
    suggestions: list[str]


class MatchResult(BaseModel):
    target: Literal["opportunity", "posting"]
    target_id: int
    target_label: str  # "Company — Role", for cards and headers
    best_resume_id: int | None
    per_resume: list[ResumeMatch]
    jd_source: Literal["opportunity", "posting"]
    cached: bool
    model: str | None


class ProfileRead(ORMModel):
    title_keywords: list[str]
    locations: list[str]
    work_modes: list[str]
    min_vector_score: float
    enabled: bool
    last_refreshed_at: datetime | None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title_keywords: list[str] | None = Field(None, max_length=6)
    locations: list[str] | None = Field(None, max_length=5)
    work_modes: list[WorkModeText] | None = Field(None, max_length=3)
    min_vector_score: float | None = Field(None, ge=0.3, le=0.95)
    enabled: bool | None = None

    @field_validator("title_keywords", "locations")
    @classmethod
    def _clean(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [" ".join(v.split())[:100] for v in value if v.strip()]
        return list(dict.fromkeys(cleaned))


class RecommendationRead(BaseModel):
    id: int
    job: JobPostingRead
    vector_score: float
    best_resume_id: int | None
    best_resume_label: str | None
    created_at: datetime


class RefreshResponse(BaseModel):
    added: int
    considered: int
    notices: list[Notice]
