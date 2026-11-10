from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.analytics import AnalyticsService
from app.services.contact import ContactService
from app.services.daily_log import DailyLogService
from app.services.dashboard import DashboardService
from app.services.followup import FollowupService
from app.services.interaction import InteractionService
from app.services.opportunity import OpportunityService
from app.services.prep_item import PrepItemService
from app.services.resume import ResumeService
from app.services.weekly_target import WeeklyTargetService

DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_clock(settings: SettingsDep) -> Clock:
    return Clock(tz=ZoneInfo(settings.timezone))


ClockDep = Annotated[Clock, Depends(get_clock)]


def get_opportunity_service(
    db: DbSession, clock: ClockDep, settings: SettingsDep
) -> OpportunityService:
    return OpportunityService(db, clock, settings)


def get_contact_service(db: DbSession) -> ContactService:
    return ContactService(db)


def get_interaction_service(db: DbSession, clock: ClockDep) -> InteractionService:
    return InteractionService(db, clock)


def get_followup_service(db: DbSession, clock: ClockDep) -> FollowupService:
    return FollowupService(db, clock)


def get_dashboard_service(db: DbSession, clock: ClockDep) -> DashboardService:
    return DashboardService(db, clock)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
OpportunityServiceDep = Annotated[OpportunityService, Depends(get_opportunity_service)]
ContactServiceDep = Annotated[ContactService, Depends(get_contact_service)]
InteractionServiceDep = Annotated[InteractionService, Depends(get_interaction_service)]
FollowupServiceDep = Annotated[FollowupService, Depends(get_followup_service)]


def get_daily_log_service(db: DbSession, clock: ClockDep) -> DailyLogService:
    return DailyLogService(db, clock)


def get_weekly_target_service(db: DbSession) -> WeeklyTargetService:
    return WeeklyTargetService(db)


def get_prep_item_service(db: DbSession) -> PrepItemService:
    return PrepItemService(db)


def get_analytics_service(db: DbSession, clock: ClockDep) -> AnalyticsService:
    return AnalyticsService(db, clock)


DailyLogServiceDep = Annotated[DailyLogService, Depends(get_daily_log_service)]
WeeklyTargetServiceDep = Annotated[WeeklyTargetService, Depends(get_weekly_target_service)]
PrepItemServiceDep = Annotated[PrepItemService, Depends(get_prep_item_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


def get_resume_service(db: DbSession) -> ResumeService:
    return ResumeService(db)


ResumeServiceDep = Annotated[ResumeService, Depends(get_resume_service)]
