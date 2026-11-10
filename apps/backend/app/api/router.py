from fastapi import APIRouter

from app.api import contacts, dashboard, followups, health, interactions, opportunities

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(opportunities.router)
api_router.include_router(contacts.router)
api_router.include_router(dashboard.router)
api_router.include_router(interactions.router)
api_router.include_router(followups.router)
