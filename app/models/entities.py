from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import (
    AgentLogStatus,
    DailyPlanStatus,
    GoalStatus,
    GoalType,
    NotificationStatus,
    NotificationType,
    PlanItemStatus,
    PlanItemType,
    TaskPriority,
    TaskStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, min_length=1, max_length=120)
    email: str = Field(index=True, unique=True, min_length=3, max_length=255)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class Goal(SQLModel, table=True):
    __tablename__ = "goals"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    goal_type: GoalType = Field(index=True, nullable=False)
    target_value: float = Field(default=1.0, gt=0)
    current_value: float = Field(default=0.0, ge=0)
    unit: str = Field(default="points", min_length=1, max_length=50)
    start_date: date
    end_date: date
    status: GoalStatus = Field(default=GoalStatus.ACTIVE, index=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, index=True, nullable=False)
    deadline: datetime | None = Field(default=None, index=True)
    estimated_minutes: int = Field(default=30, ge=15, le=480)
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True, nullable=False)
    goal_id: int | None = Field(default=None, foreign_key="goals.id", index=True)
    goal_progress_value: float = Field(default=0.0, ge=0)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    completed_at: datetime | None = None


class CalendarEvent(SQLModel, table=True):
    __tablename__ = "calendar_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    title: str = Field(min_length=1, max_length=200)
    start_time: datetime = Field(index=True, nullable=False)
    end_time: datetime = Field(index=True, nullable=False)
    source: str = Field(default="mock", min_length=1, max_length=50)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class DailyPlan(SQLModel, table=True):
    __tablename__ = "daily_plans"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    plan_date: date = Field(index=True, nullable=False)
    status: DailyPlanStatus = Field(default=DailyPlanStatus.DRAFT, index=True, nullable=False)
    retry_count: int = Field(default=0, ge=0)
    validation_summary: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class DailyPlanItem(SQLModel, table=True):
    __tablename__ = "daily_plan_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="daily_plans.id", index=True, nullable=False)
    task_id: int | None = Field(default=None, foreign_key="tasks.id", index=True)
    item_type: PlanItemType = Field(default=PlanItemType.TASK, index=True, nullable=False)
    start_time: datetime = Field(index=True, nullable=False)
    end_time: datetime = Field(index=True, nullable=False)
    reason: str = Field(min_length=1, max_length=500)
    status: PlanItemStatus = Field(default=PlanItemStatus.SCHEDULED, index=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class AgentLog(SQLModel, table=True):
    __tablename__ = "agent_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: int | None = Field(default=None, foreign_key="daily_plans.id", index=True)
    context_date: date | None = Field(default=None, index=True)
    agent_name: str = Field(index=True, min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=200)
    input_summary: str = Field(min_length=1, max_length=1000)
    output_summary: str = Field(min_length=1, max_length=1000)
    status: AgentLogStatus = Field(default=AgentLogStatus.SUCCESS, index=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    message: str = Field(min_length=1, max_length=500)
    notification_type: NotificationType = Field(
        default=NotificationType.MORNING_CHECKIN,
        index=True,
        nullable=False,
    )
    status: NotificationStatus = Field(
        default=NotificationStatus.UNREAD,
        index=True,
        nullable=False,
    )
    context_date: date | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    read_at: datetime | None = None
