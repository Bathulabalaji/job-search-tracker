from typing import Annotated

from fastapi import Depends
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.api.auth_deps import (
    ClockDep,
    CurrentUser,
    DbSession,
    LLMProvidersDep,
    SettingsDep,
    get_checkpointer,
    get_session_scope,
)
from app.assistant.runner import SessionScope, TurnRunner
from app.services.analytics import AnalyticsService
from app.services.chat import ChatService
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


def get_chat_service(
    db: DbSession, clock: ClockDep, settings: SettingsDep, user: CurrentUser
) -> ChatService:
    return ChatService(db, clock, settings, user.id)


CheckpointerDep = Annotated[BaseCheckpointSaver[str], Depends(get_checkpointer)]


def get_turn_runner(
    settings: SettingsDep,
    clock: ClockDep,
    user: CurrentUser,
    providers: LLMProvidersDep,
    checkpointer: CheckpointerDep,
    session_scope: Annotated[SessionScope, Depends(get_session_scope)],
) -> TurnRunner:
    return TurnRunner(
        session_scope=session_scope,
        settings=settings,
        clock=clock,
        providers=providers,
        checkpointer=checkpointer,
        user_id=user.id,
        first_name=(user.full_name.split() or ["there"])[0],
    )


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
TurnRunnerDep = Annotated[TurnRunner, Depends(get_turn_runner)]
