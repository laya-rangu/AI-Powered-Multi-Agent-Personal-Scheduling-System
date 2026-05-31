from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import get_session
from app.core.config import get_settings
from app.models.entities import DailyPlan
from app.models.schemas import (
    DailyCheckInRequest,
    DailyCheckInResponse,
    DailyPlanGenerateRequest,
    DailyPlanRead,
)
from app.services.daily_checkin import run_daily_checkin
from app.services.daily_planner import build_daily_plan_read, compute_daily_plan, save_daily_plan


router = APIRouter(prefix="/daily", tags=["daily"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/checkin", response_model=DailyCheckInResponse, status_code=status.HTTP_201_CREATED)
def daily_checkin(payload: DailyCheckInRequest, session: SessionDep) -> DailyCheckInResponse:
    result = run_daily_checkin(
        session,
        message=payload.message,
        target_date=payload.checkin_date or date.today(),
        persist_tasks=payload.persist_tasks,
        model=payload.model,
    )
    return result.response


@router.post("/plan", response_model=DailyPlanRead, status_code=status.HTTP_201_CREATED)
def generate_daily_plan(payload: DailyPlanGenerateRequest, session: SessionDep) -> DailyPlanRead:
    computation = compute_daily_plan(session, payload.plan_date)
    plan = save_daily_plan(session, payload.plan_date, computation)
    return build_daily_plan_read(session, plan, unscheduled_override=computation.unscheduled_tasks)


@router.get("/plan", response_model=DailyPlanRead)
def get_daily_plan(
    session: SessionDep,
    target_date: Annotated[date, Query(alias="date")],
) -> DailyPlanRead:
    settings = get_settings()
    plan = session.exec(
        select(DailyPlan).where(
            DailyPlan.user_id == settings.default_user_id,
            DailyPlan.plan_date == target_date,
        )
    ).first()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily plan not found")
    return build_daily_plan_read(session, plan)
