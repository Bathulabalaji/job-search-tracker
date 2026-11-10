from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DailyLogServiceDep
from app.models.daily_log import DailyLog
from app.schemas.daily_log import DailyLogCreate, DailyLogRead, DailyLogUpdate, StreakRead

router = APIRouter(prefix="/daily-logs", tags=["daily-logs"])


@router.get("", response_model=list[DailyLogRead])
def list_daily_logs(
    service: DailyLogServiceDep,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=366)] = 60,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DailyLog]:
    """Newest first."""
    return service.list(date_from=date_from, date_to=date_to, limit=limit, offset=offset)


@router.get("/streak", response_model=StreakRead)
def get_streak(service: DailyLogServiceDep) -> StreakRead:
    """Consecutive days with recorded activity; today is not counted against you until it ends."""
    return service.streak()


@router.post("", response_model=DailyLogRead, status_code=status.HTTP_201_CREATED)
def create_daily_log(data: DailyLogCreate, service: DailyLogServiceDep) -> DailyLog:
    return service.create(data)


@router.get("/{log_id}", response_model=DailyLogRead)
def get_daily_log(log_id: int, service: DailyLogServiceDep) -> DailyLog:
    return service.get(log_id)


@router.patch("/{log_id}", response_model=DailyLogRead)
def update_daily_log(log_id: int, data: DailyLogUpdate, service: DailyLogServiceDep) -> DailyLog:
    return service.update(log_id, data)


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_daily_log(log_id: int, service: DailyLogServiceDep) -> Response:
    service.delete(log_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
