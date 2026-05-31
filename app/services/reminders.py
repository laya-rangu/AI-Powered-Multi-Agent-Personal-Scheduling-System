from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.core.config import get_settings
from app.db import engine
from app.services.notifications import current_local_date, ensure_morning_checkin_notification_for_date


class ReminderScheduler:
    def __init__(self) -> None:
        self._scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        settings = get_settings()
        if not settings.enable_reminder_scheduler:
            return
        if self._scheduler is not None and self._scheduler.running:
            return

        timezone = ZoneInfo(settings.app_timezone)
        scheduler = BackgroundScheduler(timezone=timezone)
        scheduler.add_job(
            create_today_morning_checkin_notification,
            CronTrigger(
                hour=settings.morning_checkin_time.hour,
                minute=settings.morning_checkin_time.minute,
                timezone=timezone,
            ),
            id="morning-checkin-reminder",
            replace_existing=True,
        )
        scheduler.start()
        self._scheduler = scheduler

    def shutdown(self) -> None:
        if self._scheduler is None:
            return
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self._scheduler = None


reminder_scheduler = ReminderScheduler()


def create_today_morning_checkin_notification() -> None:
    create_morning_checkin_notification_for_date(current_local_date())


def create_morning_checkin_notification_for_date(target_date: date) -> None:
    with Session(engine) as session:
        ensure_morning_checkin_notification_for_date(session, target_date)
