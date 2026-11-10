from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.contact import ContactService
from app.services.followup import FollowupService
from app.services.interaction import InteractionService
from app.services.opportunity import OpportunityService

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


OpportunityServiceDep = Annotated[OpportunityService, Depends(get_opportunity_service)]
ContactServiceDep = Annotated[ContactService, Depends(get_contact_service)]
InteractionServiceDep = Annotated[InteractionService, Depends(get_interaction_service)]
FollowupServiceDep = Annotated[FollowupService, Depends(get_followup_service)]
