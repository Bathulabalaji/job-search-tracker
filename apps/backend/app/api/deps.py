from typing import Annotated

from fastapi import Depends

from app.api.auth_deps import ClockDep, CurrentUser, DbSession, SettingsDep
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


def get_opportunity_service(
    db: DbSession, clock: ClockDep, settings: SettingsDep, user: CurrentUser
) -> OpportunityService:
    return OpportunityService(db, clock, settings, user.id)


def get_contact_service(db: DbSession, user: CurrentUser) -> ContactService:
    return ContactService(db, user.id)


def get_interaction_service(
    db: DbSession, clock: ClockDep, user: CurrentUser
) -> InteractionService:
    return InteractionService(db, clock, user.id)


def get_followup_service(db: DbSession, clock: ClockDep, user: CurrentUser) -> FollowupService:
    return FollowupService(db, clock, user.id)


def get_dashboard_service(db: DbSession, clock: ClockDep, user: CurrentUser) -> DashboardService:
    return DashboardService(db, clock, user.id)


def get_daily_log_service(db: DbSession, clock: ClockDep, user: CurrentUser) -> DailyLogService:
    return DailyLogService(db, clock, user.id)


def get_weekly_target_service(db: DbSession, user: CurrentUser) -> WeeklyTargetService:
    return WeeklyTargetService(db, user.id)


def get_prep_item_service(db: DbSession, user: CurrentUser) -> PrepItemService:
    return PrepItemService(db, user.id)


def get_analytics_service(db: DbSession, clock: ClockDep, user: CurrentUser) -> AnalyticsService:
    return AnalyticsService(db, clock, user.id)


def get_resume_service(db: DbSession, user: CurrentUser) -> ResumeService:
    return ResumeService(db, user.id)


OpportunityServiceDep = Annotated[OpportunityService, Depends(get_opportunity_service)]
ContactServiceDep = Annotated[ContactService, Depends(get_contact_service)]
InteractionServiceDep = Annotated[InteractionService, Depends(get_interaction_service)]
FollowupServiceDep = Annotated[FollowupService, Depends(get_followup_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
DailyLogServiceDep = Annotated[DailyLogService, Depends(get_daily_log_service)]
WeeklyTargetServiceDep = Annotated[WeeklyTargetService, Depends(get_weekly_target_service)]
PrepItemServiceDep = Annotated[PrepItemService, Depends(get_prep_item_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
ResumeServiceDep = Annotated[ResumeService, Depends(get_resume_service)]
