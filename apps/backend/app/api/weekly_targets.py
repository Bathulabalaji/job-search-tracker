from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import WeeklyTargetServiceDep
from app.models.weekly_target import WeeklyTarget
from app.schemas.weekly_target import WeeklyTargetCreate, WeeklyTargetRead, WeeklyTargetUpdate

router = APIRouter(prefix="/weekly-targets", tags=["weekly-targets"])


@router.get("", response_model=list[WeeklyTargetRead])
def list_weekly_targets(
    service: WeeklyTargetServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 52,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[WeeklyTarget]:
    """Newest week first."""
    return service.list(limit=limit, offset=offset)


@router.post("", response_model=WeeklyTargetRead, status_code=status.HTTP_201_CREATED)
def create_weekly_target(data: WeeklyTargetCreate, service: WeeklyTargetServiceDep) -> WeeklyTarget:
    """`week_start` must be a Monday. One row per week."""
    return service.create(data)


@router.get("/{target_id}", response_model=WeeklyTargetRead)
def get_weekly_target(target_id: int, service: WeeklyTargetServiceDep) -> WeeklyTarget:
    return service.get(target_id)


@router.patch("/{target_id}", response_model=WeeklyTargetRead)
def update_weekly_target(
    target_id: int, data: WeeklyTargetUpdate, service: WeeklyTargetServiceDep
) -> WeeklyTarget:
    return service.update(target_id, data)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_weekly_target(target_id: int, service: WeeklyTargetServiceDep) -> Response:
    service.delete(target_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
