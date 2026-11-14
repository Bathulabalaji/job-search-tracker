"""Endpoints for the operator's scheduled jobs, not for app users."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.api.auth_deps import ClockDep, DbSession, SettingsDep
from app.api.deps import CheckpointerDep
from app.core.errors import AuthError
from app.services.maintenance import MaintenanceService

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/maintenance")
def run_maintenance(
    settings: SettingsDep,
    db: DbSession,
    clock: ClockDep,
    checkpointer: CheckpointerDep,
    x_maintenance_secret: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    """Expire, archive and delete what has aged out. Safe to call as often as you like."""
    if not settings.maintenance_secret:
        # Not configured: behave as if the route did not exist.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    if x_maintenance_secret is None or not hmac.compare_digest(
        x_maintenance_secret.encode(), settings.maintenance_secret.encode()
    ):
        raise AuthError("bad_maintenance_secret", "That maintenance secret is not valid.", 403)
    return MaintenanceService(db, clock, settings, checkpointer).run().as_json()
