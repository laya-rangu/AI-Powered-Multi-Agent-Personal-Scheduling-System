from __future__ import annotations

from datetime import date, datetime

from pydantic import model_validator
from sqlmodel import Field, SQLModel

from app.models.enums import (
    AgentLogStatus,
    DailyPlanStatus,
    ExtractionSource,
    GoalStatus,
    GoalType,
    NotificationStatus,
    NotificationType,
    PlanItemStatus,
    PlanItemType,
    TaskPriority,
    TaskStatus,
)


class TaskBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    deadline: datetime | None = None
    estimated_minutes: int = Field(default=30, ge=15, le=480)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    goal_id: int | None = None
    goal_progress_value: float = Field(default=0.0, ge=0)


class TaskCreate(TaskBase):
    pass


class TaskUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority | None = None
    deadline: datetime | None = None
    estimated_minutes: int | None = Field(default=None, ge=15, le=480)
    status: TaskStatus | None = None
    goal_id: int | None = None
    goal_progress_value: float | None = Field(default=None, ge=0)


class TaskRead(TaskBase):
    id: int
    user_id: int
    created_at: datetime
    completed_at: datetime | None = None


class GoalBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    goal_type: GoalType
    target_value: float = Field(gt=0)
    current_value: float = Field(default=0.0, ge=0)
    unit: str = Field(default="points", min_length=1, max_length=50)
    start_date: date
    end_date: date
    status: GoalStatus = Field(default=GoalStatus.ACTIVE)


class GoalCreate(GoalBase):
    @model_validator(mode="after")
    def validate_dates(self) -> "GoalCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class GoalUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    goal_type: GoalType | None = None
    target_value: float | None = Field(default=None, gt=0)
    current_value: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    status: GoalStatus | None = None


class GoalRead(GoalBase):
    id: int
    user_id: int
    created_at: datetime
    progress_percentage: float


class GoalProgressSnapshot(SQLModel):
    id: int
    title: str
    goal_type: GoalType
    status: GoalStatus
    current_value: float
    target_value: float
    unit: str
    linked_completed_tasks: int
    progress_percentage: float


class CalendarEventBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    start_time: datetime
    end_time: datetime
    source: str = Field(default="mock", min_length=1, max_length=50)


class CalendarEventCreate(CalendarEventBase):
    @model_validator(mode="after")
    def validate_time_range(self) -> "CalendarEventCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CalendarEventRead(CalendarEventBase):
    id: int
    user_id: int
    created_at: datetime


class FreeSlotRead(SQLModel):
    start_time: datetime
    end_time: datetime
    duration_minutes: int


class DailyPlanGenerateRequest(SQLModel):
    plan_date: date = Field(alias="date")


class DailyPlanItemRead(SQLModel):
    id: int
    task_id: int | None = None
    task_title: str | None = None
    item_type: PlanItemType
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    reason: str
    status: PlanItemStatus


class UnscheduledTaskRead(SQLModel):
    task_id: int
    title: str
    priority: TaskPriority
    remaining_minutes: int
    reason: str


class DailyPlanRead(SQLModel):
    id: int
    user_id: int
    plan_date: date
    status: DailyPlanStatus
    retry_count: int
    validation_summary: str | None = None
    created_at: datetime
    items: list[DailyPlanItemRead]
    unscheduled_tasks: list[UnscheduledTaskRead]


class AgentLogRead(SQLModel):
    id: int
    plan_id: int | None = None
    context_date: date | None = None
    agent_name: str
    action: str
    input_summary: str
    output_summary: str
    status: AgentLogStatus
    created_at: datetime


class ExtractedTaskCandidate(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    estimated_minutes: int = Field(default=30, ge=15, le=480)
    deadline: datetime | None = None


class DailyCheckInRequest(SQLModel):
    message: str = Field(min_length=3, max_length=6000)
    checkin_date: date | None = Field(default=None, alias="date")
    persist_tasks: bool = True
    model: str | None = None


class DailyCheckInResponse(SQLModel):
    checkin_date: date = Field(alias="date")
    model: str
    source: ExtractionSource
    used_fallback: bool
    extracted_tasks: list[ExtractedTaskCandidate]
    created_tasks: list[TaskRead]
    warnings: list[str]


class AssistantDailyPlanRequest(SQLModel):
    message: str = Field(min_length=3, max_length=6000)
    target_date: date = Field(alias="date")
    model: str | None = None


class WorkflowStepRead(SQLModel):
    node_name: str
    agent_name: str
    summary: str
    status: AgentLogStatus


class AssistantDailyPlanResponse(SQLModel):
    workflow_date: date = Field(alias="date")
    model: str
    source: ExtractionSource
    used_fallback: bool
    warnings: list[str]
    extracted_tasks: list[ExtractedTaskCandidate]
    created_tasks: list[TaskRead]
    daily_plan: DailyPlanRead
    workflow_steps: list[WorkflowStepRead]


class NotificationRead(SQLModel):
    id: int
    user_id: int
    message: str
    notification_type: NotificationType
    status: NotificationStatus
    context_date: date | None = None
    created_at: datetime
    read_at: datetime | None = None


class NotificationUpdate(SQLModel):
    status: NotificationStatus


class DashboardPlanSummary(SQLModel):
    plan_id: int
    status: DailyPlanStatus
    scheduled_item_count: int
    unscheduled_task_count: int


class DashboardTodayResponse(SQLModel):
    dashboard_date: date = Field(alias="date")
    morning_checkin_prompt: NotificationRead | None = None
    unread_notifications_count: int
    pending_tasks_count: int
    today_plan: DashboardPlanSummary | None = None
