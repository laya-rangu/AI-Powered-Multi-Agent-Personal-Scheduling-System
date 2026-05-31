from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.entities import DailyPlan, DailyPlanItem, Notification, Task
from app.models.enums import NotificationStatus, NotificationType, TaskStatus
from app.models.schemas import DashboardPlanSummary, DashboardTodayResponse, NotificationRead


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def current_local_date() -> date:
    settings = get_settings()
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def morning_checkin_message() -> str:
    return "Good morning! What are your top tasks for today?"


def ensure_morning_checkin_notification_for_date(
    session: Session,
    target_date: date,
) -> Notification:
    settings = get_settings()
    existing = session.exec(
        select(Notification).where(
            Notification.user_id == settings.default_user_id,
            Notification.notification_type == NotificationType.MORNING_CHECKIN,
            Notification.context_date == target_date,
        )
    ).first()
    if existing is not None:
        return existing

    notification = Notification(
        user_id=settings.default_user_id,
        message=morning_checkin_message(),
        notification_type=NotificationType.MORNING_CHECKIN,
        status=NotificationStatus.UNREAD,
        context_date=target_date,
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def mark_morning_checkin_complete_for_date(session: Session, target_date: date) -> int:
    settings = get_settings()
    notifications = session.exec(
        select(Notification).where(
            Notification.user_id == settings.default_user_id,
            Notification.notification_type == NotificationType.MORNING_CHECKIN,
            Notification.context_date == target_date,
            Notification.status == NotificationStatus.UNREAD,
        )
    ).all()

    updated = 0
    for notification in notifications:
        notification.status = NotificationStatus.READ
        notification.read_at = _utc_now()
        session.add(notification)
        updated += 1
    return updated


def list_notifications(
    session: Session,
    *,
    status_filter: NotificationStatus | None = None,
) -> list[Notification]:
    settings = get_settings()
    statement = (
        select(Notification)
        .where(Notification.user_id == settings.default_user_id)
        .order_by(Notification.context_date.desc(), Notification.created_at.desc())
    )
    if status_filter is not None:
        statement = statement.where(Notification.status == status_filter)
    return list(session.exec(statement))


def get_notification_or_none(session: Session, notification_id: int) -> Notification | None:
    settings = get_settings()
    notification = session.get(Notification, notification_id)
    if notification is None or notification.user_id != settings.default_user_id:
        return None
    return notification


def build_dashboard_today(session: Session, target_date: date) -> DashboardTodayResponse:
    settings = get_settings()
    morning_prompt = session.exec(
        select(Notification).where(
            Notification.user_id == settings.default_user_id,
            Notification.notification_type == NotificationType.MORNING_CHECKIN,
            Notification.context_date == target_date,
            Notification.status == NotificationStatus.UNREAD,
        )
    ).first()

    unread_notifications_count = len(
        session.exec(
            select(Notification).where(
                Notification.user_id == settings.default_user_id,
                Notification.status == NotificationStatus.UNREAD,
            )
        ).all()
    )

    pending_tasks_count = len(
        session.exec(
            select(Task).where(
                Task.user_id == settings.default_user_id,
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            )
        ).all()
    )

    plan = session.exec(
        select(DailyPlan).where(
            DailyPlan.user_id == settings.default_user_id,
            DailyPlan.plan_date == target_date,
        )
    ).first()

    today_plan = None
    if plan is not None:
        from app.services.daily_planner import build_daily_plan_read

        plan_read = build_daily_plan_read(session, plan)
        scheduled_item_count = len(
            session.exec(
                select(DailyPlanItem).where(DailyPlanItem.plan_id == plan.id)
            ).all()
        )
        today_plan = DashboardPlanSummary(
            plan_id=plan.id,
            status=plan.status,
            scheduled_item_count=scheduled_item_count,
            unscheduled_task_count=len(plan_read.unscheduled_tasks),
        )

    return DashboardTodayResponse(
        date=target_date,
        morning_checkin_prompt=(
            NotificationRead.model_validate(morning_prompt) if morning_prompt is not None else None
        ),
        unread_notifications_count=unread_notifications_count,
        pending_tasks_count=pending_tasks_count,
        today_plan=today_plan,
    )
