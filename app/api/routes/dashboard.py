from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_session
from app.models.schemas import DashboardTodayResponse
from app.services.notifications import (
    build_dashboard_today,
    current_local_date,
    ensure_morning_checkin_notification_for_date,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/today", response_model=DashboardTodayResponse)
def get_dashboard_today(session: SessionDep) -> DashboardTodayResponse:
    today = current_local_date()
    ensure_morning_checkin_notification_for_date(session, today)
    return build_dashboard_today(session, today)
