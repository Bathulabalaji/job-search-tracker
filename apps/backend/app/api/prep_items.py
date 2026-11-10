from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import PrepItemServiceDep
from app.models.enums import PrepCategory, PrepStatus
from app.models.prep_item import PrepItem
from app.schemas.prep_item import PrepItemCreate, PrepItemRead, PrepItemUpdate

router = APIRouter(prefix="/prep-items", tags=["prep-items"])


@router.get("", response_model=list[PrepItemRead])
def list_prep_items(
    service: PrepItemServiceDep,
    category: PrepCategory | None = None,
    status_: Annotated[PrepStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(description="Search topic")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PrepItem]:
    return service.list(category=category, status=status_, q=q, limit=limit, offset=offset)


@router.post("", response_model=PrepItemRead, status_code=status.HTTP_201_CREATED)
def create_prep_item(data: PrepItemCreate, service: PrepItemServiceDep) -> PrepItem:
    return service.create(data)


@router.get("/{item_id}", response_model=PrepItemRead)
def get_prep_item(item_id: int, service: PrepItemServiceDep) -> PrepItem:
    return service.get(item_id)


@router.patch("/{item_id}", response_model=PrepItemRead)
def update_prep_item(item_id: int, data: PrepItemUpdate, service: PrepItemServiceDep) -> PrepItem:
    return service.update(item_id, data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prep_item(item_id: int, service: PrepItemServiceDep) -> Response:
    service.delete(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
