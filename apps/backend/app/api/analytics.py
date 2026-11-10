from datetime import date

from fastapi import APIRouter

from app.api.deps import AnalyticsServiceDep
from app.schemas.analytics import WeeklyAnalytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/weekly", response_model=WeeklyAnalytics)
def weekly_analytics(service: AnalyticsServiceDep, week_of: date | None = None) -> WeeklyAnalytics:
    """Daily-log totals vs weekly target, 8-week trend, funnel conversion and response rates.

    `week_of` can be any date; it is normalised to that week's Monday. Defaults to this week.
    """
    return service.weekly(week_of)
