"""Job search over public search APIs. The assistant uses the same service through its tools."""

from fastapi import APIRouter, status

from app.api.deps import JobSearchServiceDep
from app.schemas.job import JobPostingRead, JobSearchRequest, JobSearchResponse, TrackJobRequest
from app.schemas.opportunity import OpportunityRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/search", response_model=JobSearchResponse)
def search_jobs(data: JobSearchRequest, service: JobSearchServiceDep) -> JobSearchResponse:
    return service.search(data)


@router.get("/{posting_id}", response_model=JobPostingRead)
def get_job(posting_id: int, service: JobSearchServiceDep) -> JobPostingRead:
    return service.get(posting_id)


@router.post(
    "/{posting_id}/track", response_model=OpportunityRead, status_code=status.HTTP_201_CREATED
)
def track_job(
    posting_id: int, data: TrackJobRequest, service: JobSearchServiceDep
) -> OpportunityRead:
    return service.track(posting_id, data)


@router.post("/{posting_id}/check", response_model=JobPostingRead)
def check_job(posting_id: int, service: JobSearchServiceDep) -> JobPostingRead:
    return service.check(posting_id)
