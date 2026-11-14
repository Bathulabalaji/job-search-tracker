from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from app.api.auth_deps import (
    ClockDep,
    CurrentUser,
    DbSession,
    LLMGatewayDep,
    LLMProvidersDep,
    SettingsDep,
    get_checkpointer,
    get_session_scope,
)
from app.assistant.runner import SessionScope, TurnRunner
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AuthError
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
from app.services.resume_documents import (
    ResumeDocumentService,
    embed_later,
    verify_download_token,
)
from app.services.weekly_target import WeeklyTargetService
from app.storage import build_object_store
from app.storage.object_store import ObjectStore


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


CheckpointerDep = Annotated[BaseCheckpointSaver[str], Depends(get_checkpointer)]


def get_chat_service(
    db: DbSession,
    clock: ClockDep,
    settings: SettingsDep,
    user: CurrentUser,
    checkpointer: CheckpointerDep,
) -> ChatService:
    return ChatService(db, clock, settings, user.id, checkpointer)


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


# ---- resume files (Phase 2) -------------------------------------------------------------------


def get_object_store(settings: SettingsDep) -> ObjectStore:
    return build_object_store(settings)


ObjectStoreDep = Annotated[ObjectStore, Depends(get_object_store)]


def get_resume_document_service(
    db: DbSession,
    clock: ClockDep,
    settings: SettingsDep,
    user: CurrentUser,
    store: ObjectStoreDep,
    gateway: LLMGatewayDep,
) -> ResumeDocumentService:
    return ResumeDocumentService(db, clock, settings, user.id, store, gateway)


ResumeDocumentServiceDep = Annotated[ResumeDocumentService, Depends(get_resume_document_service)]

type EmbedLater = Callable[[int], None]


def get_embed_later(
    settings: SettingsDep,
    clock: ClockDep,
    user: CurrentUser,
    store: ObjectStoreDep,
    providers: LLMProvidersDep,
    session_scope: Annotated[SessionScope, Depends(get_session_scope)],
) -> EmbedLater:
    """A background task that indexes one resume (embeddings + profile) after the response."""

    def run(resume_id: int) -> None:
        embed_later(session_scope, settings, clock, user.id, resume_id, store, providers)

    return run


EmbedLaterDep = Annotated[EmbedLater, Depends(get_embed_later)]


def build_document_service_for_token(
    db: Session, settings: Settings, clock: Clock, store: ObjectStore, token: str, resume_id: int
) -> ResumeDocumentService:
    """For the signed download link: no sign-in, the token says whose file this is."""
    user_id = verify_download_token(settings.secret_key, token, resume_id, now=clock.now())
    if user_id is None:
        raise AuthError("invalid_link", "This download link is invalid or has expired.", 403)
    return ResumeDocumentService(db, clock, settings, user_id, store, None)
