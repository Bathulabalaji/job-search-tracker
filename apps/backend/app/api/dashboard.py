from fastapi import APIRouter

from app.api.deps import DashboardServiceDep
from app.schemas.dashboard import SummaryResponse, TodayResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/today", response_model=TodayResponse)
def today(service: DashboardServiceDep) -> TodayResponse:
    """Pending follow-ups due or overdue, interviews today, and the top 3 next actions."""
    return service.today()


@router.get("/summary", response_model=SummaryResponse)
def summary(service: DashboardServiceDep) -> SummaryResponse:
    """Counts per stage, response rate and interviews this week (Mon-Sun)."""
    return service.summary()
