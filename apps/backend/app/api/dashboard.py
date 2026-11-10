from fastapi import APIRouter

from app.api.deps import DashboardServiceDep
from app.schemas.dashboard import TodayResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/today", response_model=TodayResponse)
def today(service: DashboardServiceDep) -> TodayResponse:
    """Pending follow-ups due or overdue, interviews today, and the top 3 next actions."""
    return service.today()
