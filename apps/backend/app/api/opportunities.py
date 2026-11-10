from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import OpportunityServiceDep
from app.models.enums import Source, Stage
from app.schemas.opportunity import (
    MoveRequest,
    MoveResponse,
    OpportunityCreate,
    OpportunityRead,
    OpportunityUpdate,
)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("", response_model=list[OpportunityRead])
def list_opportunities(
    service: OpportunityServiceDep,
    stage: Stage | None = None,
    priority: Annotated[int | None, Query(ge=1, le=3)] = None,
    source: Source | None = None,
    q: Annotated[str | None, Query(description="Search company or role")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OpportunityRead]:
    return service.list(
        stage=stage, priority=priority, source=source, q=q, limit=limit, offset=offset
    )


@router.post("", response_model=OpportunityRead, status_code=status.HTTP_201_CREATED)
def create_opportunity(data: OpportunityCreate, service: OpportunityServiceDep) -> OpportunityRead:
    return service.create(data)


@router.get("/{opportunity_id}", response_model=OpportunityRead)
def get_opportunity(opportunity_id: int, service: OpportunityServiceDep) -> OpportunityRead:
    return service.get(opportunity_id)


@router.patch("/{opportunity_id}", response_model=OpportunityRead)
def update_opportunity(
    opportunity_id: int, data: OpportunityUpdate, service: OpportunityServiceDep
) -> OpportunityRead:
    return service.update(opportunity_id, data)


@router.delete("/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opportunity(opportunity_id: int, service: OpportunityServiceDep) -> Response:
    service.delete(opportunity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{opportunity_id}/move", response_model=MoveResponse)
def move_opportunity(
    opportunity_id: int, data: MoveRequest, service: OpportunityServiceDep
) -> MoveResponse:
    """Change stage, record a `stage_change` interaction, and apply the follow-up auto-rule."""
    return service.move(opportunity_id, data)
