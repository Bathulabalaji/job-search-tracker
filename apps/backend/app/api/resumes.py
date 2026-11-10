from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import ResumeServiceDep
from app.models.resume import Resume
from app.schemas.resume import ResumeCreate, ResumeRead, ResumeUpdate

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("", response_model=list[ResumeRead])
def list_resumes(
    service: ResumeServiceDep,
    q: Annotated[str | None, Query(description="Search label, focus or file name")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Resume]:
    return service.list(q=q, limit=limit, offset=offset)


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def create_resume(data: ResumeCreate, service: ResumeServiceDep) -> Resume:
    """Metadata only: there is no file upload."""
    return service.create(data)


@router.get("/{resume_id}", response_model=ResumeRead)
def get_resume(resume_id: int, service: ResumeServiceDep) -> Resume:
    return service.get(resume_id)


@router.patch("/{resume_id}", response_model=ResumeRead)
def update_resume(resume_id: int, data: ResumeUpdate, service: ResumeServiceDep) -> Resume:
    return service.update(resume_id, data)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int, service: ResumeServiceDep) -> Response:
    service.delete(resume_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
