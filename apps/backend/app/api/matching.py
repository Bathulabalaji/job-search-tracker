"""Which resume fits a job: for a tracked opportunity or a searched posting."""

from fastapi import APIRouter

from app.api.deps import JobMatchServiceDep
from app.schemas.match import MatchRequest, MatchResult

router = APIRouter(tags=["matching"])


@router.post("/opportunities/{opportunity_id}/match", response_model=MatchResult)
def match_opportunity(
    opportunity_id: int, data: MatchRequest, service: JobMatchServiceDep
) -> MatchResult:
    return service.match_opportunity(opportunity_id, resume_ids=data.resume_ids, force=data.force)


@router.get("/opportunities/{opportunity_id}/match", response_model=MatchResult | None)
def get_opportunity_match(opportunity_id: int, service: JobMatchServiceDep) -> MatchResult | None:
    """The stored result when nothing changed since it was computed, else null. Free."""
    return service.cached_opportunity(opportunity_id)


@router.post("/jobs/{posting_id}/match", response_model=MatchResult)
def match_posting(posting_id: int, data: MatchRequest, service: JobMatchServiceDep) -> MatchResult:
    return service.match_posting(posting_id, resume_ids=data.resume_ids, force=data.force)
