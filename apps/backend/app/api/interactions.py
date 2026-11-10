from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import InteractionServiceDep
from app.models.interaction import Interaction
from app.schemas.interaction import InteractionCreate, InteractionRead, InteractionUpdate

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.get("", response_model=list[InteractionRead])
def list_interactions(
    service: InteractionServiceDep,
    opportunity_id: int | None = None,
    contact_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Interaction]:
    """Newest first."""
    return service.list(
        opportunity_id=opportunity_id, contact_id=contact_id, limit=limit, offset=offset
    )


@router.post("", response_model=InteractionRead, status_code=status.HTTP_201_CREATED)
def create_interaction(data: InteractionCreate, service: InteractionServiceDep) -> Interaction:
    return service.create(data)


@router.get("/{interaction_id}", response_model=InteractionRead)
def get_interaction(interaction_id: int, service: InteractionServiceDep) -> Interaction:
    return service.get(interaction_id)


@router.patch("/{interaction_id}", response_model=InteractionRead)
def update_interaction(
    interaction_id: int, data: InteractionUpdate, service: InteractionServiceDep
) -> Interaction:
    return service.update(interaction_id, data)


@router.delete("/{interaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interaction(interaction_id: int, service: InteractionServiceDep) -> Response:
    service.delete(interaction_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
