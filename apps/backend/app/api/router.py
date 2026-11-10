from fastapi import APIRouter

from app.api import (
    analytics,
    contacts,
    daily_logs,
    dashboard,
    followups,
    health,
    interactions,
    opportunities,
    prep_items,
    resumes,
    weekly_targets,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(opportunities.router)
api_router.include_router(contacts.router)
api_router.include_router(dashboard.router)
api_router.include_router(interactions.router)
api_router.include_router(followups.router)
api_router.include_router(daily_logs.router)
api_router.include_router(weekly_targets.router)
api_router.include_router(prep_items.router)
api_router.include_router(analytics.router)
api_router.include_router(resumes.router)
