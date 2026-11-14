"""A structured summary of a resume, extracted once by a model and kept as JSON."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.llm.errors import LLMError
from app.llm.gateway import LLMGateway
from app.llm.policy import Task

logger = logging.getLogger("app.resumes")

PROMPT = """Extract a structured profile from this resume. Only use what the resume says;
leave lists empty rather than guessing. Skills are individual technologies, languages,
frameworks or practices (not sentences). Keep the summary under 60 words."""


class Skill(BaseModel):
    name: str = Field(max_length=60)
    years: float | None = Field(None, ge=0, le=50)


class ResumeProfile(BaseModel):
    titles: list[str] = Field(default_factory=list, max_length=8)
    years_experience: float | None = Field(None, ge=0, le=60)
    skills: list[Skill] = Field(default_factory=list, max_length=60)
    domains: list[str] = Field(default_factory=list, max_length=10)
    education: list[str] = Field(default_factory=list, max_length=6)
    locations: list[str] = Field(default_factory=list, max_length=5)
    notable_projects: list[str] = Field(default_factory=list, max_length=5)
    summary: str = Field("", max_length=600)


def extract_profile(gateway: LLMGateway, text: str) -> tuple[ResumeProfile, str] | None:
    """(profile, model) or None when no model could do it right now (not an error)."""
    prompt = [SystemMessage(content=PROMPT), HumanMessage(content=text[:12_000])]
    try:
        result = gateway.chat(
            Task.extract_structured, prompt, schema=ResumeProfile, max_tokens=1200
        )
    except LLMError as exc:
        logger.warning("resume_profile_unavailable", extra={"code": exc.code})
        return None
    if not isinstance(result.parsed, ResumeProfile):
        return None
    return result.parsed, result.model
