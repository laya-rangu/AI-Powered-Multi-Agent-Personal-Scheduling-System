from dataclasses import dataclass
from datetime import date, datetime

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.entities import CalendarEvent
from app.models.schemas import FreeSlotRead


@dataclass
class FreeSlotResult:
    events: list[CalendarEvent]
    free_slots: list[FreeSlotRead]


def _combine_day_and_time(target_date: date, raw_time) -> datetime:
    return datetime.combine(target_date, raw_time)


def get_workday_bounds(target_date: date) -> tuple[datetime, datetime]:
    settings = get_settings()
    return (
        _combine_day_and_time(target_date, settings.default_workday_start),
        _combine_day_and_time(target_date, settings.default_workday_end),
    )


def _event_bounds_for_day(event: CalendarEvent, day_start: datetime, day_end: datetime) -> tuple[datetime, datetime]:
    busy_start = max(event.start_time, day_start)
    busy_end = min(event.end_time, day_end)
    return busy_start, busy_end


def load_calendar_events_for_date(session: Session, target_date: date) -> list[CalendarEvent]:
    settings = get_settings()
    day_start, day_end = get_workday_bounds(target_date)

    statement = (
        select(CalendarEvent)
        .where(CalendarEvent.user_id == settings.default_user_id)
        .where(CalendarEvent.start_time < day_end)
        .where(CalendarEvent.end_time > day_start)
        .order_by(CalendarEvent.start_time.asc())
    )
    return list(session.exec(statement))


def calculate_free_slots_for_date(session: Session, target_date: date) -> FreeSlotResult:
    day_start, day_end = get_workday_bounds(target_date)
    events = load_calendar_events_for_date(session, target_date)

    free_slots: list[FreeSlotRead] = []
    cursor = day_start

    for event in events:
        busy_start, busy_end = _event_bounds_for_day(event, day_start, day_end)
        if busy_end <= day_start or busy_start >= day_end:
            continue

        if busy_start > cursor:
            free_slots.append(
                FreeSlotRead(
                    start_time=cursor,
                    end_time=busy_start,
                    duration_minutes=int((busy_start - cursor).total_seconds() // 60),
                )
            )

        if busy_end > cursor:
            cursor = busy_end

    if cursor < day_end:
        free_slots.append(
            FreeSlotRead(
                start_time=cursor,
                end_time=day_end,
                duration_minutes=int((day_end - cursor).total_seconds() // 60),
            )
        )

    return FreeSlotResult(events=events, free_slots=free_slots)
