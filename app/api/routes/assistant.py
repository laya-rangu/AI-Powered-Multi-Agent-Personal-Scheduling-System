from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.api.deps import get_session
from app.models.schemas import AssistantDailyPlanRequest, AssistantDailyPlanResponse
from app.services.assistant_workflow import run_assistant_daily_plan_workflow


router = APIRouter(prefix="/assistant", tags=["assistant"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/daily-plan", response_model=AssistantDailyPlanResponse, status_code=status.HTTP_201_CREATED)
def generate_assistant_daily_plan(
    payload: AssistantDailyPlanRequest,
    session: SessionDep,
) -> AssistantDailyPlanResponse:
    return run_assistant_daily_plan_workflow(session, payload)
