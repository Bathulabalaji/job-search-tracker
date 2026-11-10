from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import FollowupServiceDep
from app.models.enums import FollowupStatus
from app.models.followup import Followup
from app.schemas.followup import FollowupCreate, FollowupRead, FollowupUpdate

router = APIRouter(prefix="/followups", tags=["followups"])


@router.get("", response_model=list[FollowupRead])
def list_followups(
    service: FollowupServiceDep,
    opportunity_id: int | None = None,
    status_: Annotated[FollowupStatus | None, Query(alias="status")] = None,
    due_on_or_before: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Followup]:
    return service.list(
        opportunity_id=opportunity_id,
        status=status_,
        due_on_or_before=due_on_or_before,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=FollowupRead, status_code=status.HTTP_201_CREATED)
def create_followup(data: FollowupCreate, service: FollowupServiceDep) -> Followup:
    return service.create(data)


@router.get("/{followup_id}", response_model=FollowupRead)
def get_followup(followup_id: int, service: FollowupServiceDep) -> Followup:
    return service.get(followup_id)


@router.patch("/{followup_id}", response_model=FollowupRead)
def update_followup(
    followup_id: int, data: FollowupUpdate, service: FollowupServiceDep
) -> Followup:
    """Mark done/skipped via `status`; snooze by changing `due_date`."""
    return service.update(followup_id, data)


@router.delete("/{followup_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_followup(followup_id: int, service: FollowupServiceDep) -> Response:
    service.delete(followup_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
