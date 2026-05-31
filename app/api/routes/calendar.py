from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import get_session
from app.core.config import get_settings
from app.models.entities import CalendarEvent
from app.models.schemas import CalendarEventCreate, CalendarEventRead, FreeSlotRead
from app.services.free_slots import calculate_free_slots_for_date


router = APIRouter(prefix="/calendar", tags=["calendar"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/events", response_model=CalendarEventRead, status_code=status.HTTP_201_CREATED)
def create_calendar_event(payload: CalendarEventCreate, session: SessionDep) -> CalendarEvent:
    settings = get_settings()
    if payload.end_time <= payload.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be after start_time",
        )

    event = CalendarEvent.model_validate(payload, update={"user_id": settings.default_user_id})
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("/events", response_model=list[CalendarEventRead])
def list_calendar_events(
    session: SessionDep,
    target_date: Annotated[date, Query(alias="date")],
) -> list[CalendarEvent]:
    return calculate_free_slots_for_date(session, target_date).events


@router.get("/free-slots", response_model=list[FreeSlotRead])
def list_free_slots(
    session: SessionDep,
    target_date: Annotated[date, Query(alias="date")],
) -> list[FreeSlotRead]:
    result = calculate_free_slots_for_date(session, target_date)
    return result.free_slots

