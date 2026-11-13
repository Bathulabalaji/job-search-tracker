from fastapi import APIRouter, Depends

from app.api import (
    analytics,
    auth,
    chat,
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
from app.api.auth_deps import get_current_user, require_trusted_origin

# Every state-changing request must come from a trusted origin (CSRF defence in depth).
api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_trusted_origin)])
api_router.include_router(health.router)
api_router.include_router(auth.router)

# Everything below requires a signed-in user. The dependency also enforces the CSRF token on
# POST/PATCH/PUT/DELETE, and each service only ever sees that user's rows.
_protected = [Depends(get_current_user)]
for module in (
    opportunities,
    contacts,
    interactions,
    followups,
    dashboard,
    daily_logs,
    weekly_targets,
    prep_items,
    analytics,
    resumes,
    chat,
):
    api_router.include_router(module.router, dependencies=_protected)
