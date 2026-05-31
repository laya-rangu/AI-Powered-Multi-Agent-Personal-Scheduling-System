from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.entities import AgentLog, DailyPlan, DailyPlanItem, Task
from app.models.enums import (
    AgentLogStatus,
    DailyPlanStatus,
    PlanItemStatus,
    PlanItemType,
    TaskPriority,
    TaskStatus,
)
from app.models.schemas import DailyPlanItemRead, DailyPlanRead, UnscheduledTaskRead
from app.services.free_slots import FreeSlotResult, calculate_free_slots_for_date
from app.services.validation import ValidationReport, validate_plan_items


@dataclass
class PlannedItemDraft:
    task_id: int | None
    item_type: PlanItemType
    start_time: datetime
    end_time: datetime
    reason: str
    status: PlanItemStatus


@dataclass
class AgentLogDraft:
    agent_name: str
    action: str
    input_summary: str
    output_summary: str
    status: AgentLogStatus


@dataclass
class PlanComputation:
    items: list[PlannedItemDraft]
    unscheduled_tasks: list[UnscheduledTaskRead]
    logs: list[AgentLogDraft]
    status: DailyPlanStatus
    retry_count: int
    validation_summary: str


@dataclass
class TaskDemand:
    task: Task
    remaining_minutes: int


def _priority_rank(priority: TaskPriority) -> int:
    return {
        TaskPriority.LOW: 0,
        TaskPriority.MEDIUM: 1,
        TaskPriority.HIGH: 2,
        TaskPriority.URGENT: 3,
    }[priority]


def _deadline_key(task: Task):
    if task.deadline is None:
        return (1, task.created_at)
    return (0, task.deadline)


def _strategy_sort_key(task: Task, strategy: str):
    goal_weight = 1 if task.goal_id is not None else 0
    deadline_key = _deadline_key(task)
    if strategy == "deadline_first":
        return (deadline_key, -goal_weight, -_priority_rank(task.priority), -task.estimated_minutes)
    if strategy == "priority_first":
        return (-_priority_rank(task.priority), deadline_key, -goal_weight, -task.estimated_minutes)
    return (-_priority_rank(task.priority), deadline_key, task.estimated_minutes, -goal_weight)


def _load_plannable_tasks(session: Session, target_date: date) -> list[Task]:
    settings = get_settings()
    statement = (
        select(Task)
        .where(Task.user_id == settings.default_user_id)
        .where(Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]))
    )
    return list(session.exec(statement))


def _build_unscheduled_tasks(demands: list[TaskDemand]) -> list[UnscheduledTaskRead]:
    unscheduled = []
    for demand in demands:
        if demand.remaining_minutes <= 0:
            continue
        reason = "Not enough free time remained after higher-priority scheduling."
        if demand.remaining_minutes < demand.task.estimated_minutes:
            reason = "Task was partially scheduled and still has remaining work."
        unscheduled.append(
            UnscheduledTaskRead(
                task_id=demand.task.id,
                title=demand.task.title,
                priority=demand.task.priority,
                remaining_minutes=demand.remaining_minutes,
                reason=reason,
            )
        )
    return unscheduled


def _plan_with_strategy(tasks: list[Task], free_slots, strategy: str) -> tuple[list[PlannedItemDraft], list[TaskDemand]]:
    settings = get_settings()
    ordered_tasks = sorted(tasks, key=lambda task: _strategy_sort_key(task, strategy))
    demands = [TaskDemand(task=task, remaining_minutes=task.estimated_minutes) for task in ordered_tasks]
    items: list[PlannedItemDraft] = []
    continuous_focus_minutes = 0
    last_scheduled_end = None

    demand_index = 0
    for slot in free_slots:
        cursor = slot.start_time
        slot_end = slot.end_time
        if last_scheduled_end is None or cursor > last_scheduled_end:
            continuous_focus_minutes = 0

        while demand_index < len(demands) and demands[demand_index].remaining_minutes <= 0:
            demand_index += 1

        while cursor < slot_end and demand_index < len(demands):
            demand = demands[demand_index]
            available_minutes = int((slot_end - cursor).total_seconds() // 60)
            if available_minutes < 15:
                break

            remaining_before_break = settings.default_focus_block_minutes - continuous_focus_minutes
            if remaining_before_break <= 0:
                break_duration = settings.default_break_minutes
                if available_minutes < break_duration:
                    break

                break_end = cursor + timedelta(minutes=break_duration)
                items.append(
                    PlannedItemDraft(
                        task_id=None,
                        item_type=PlanItemType.BREAK,
                        start_time=cursor,
                        end_time=break_end,
                        reason=f"{break_duration}-minute break after a focus block.",
                        status=PlanItemStatus.INFO,
                    )
                )
                cursor = break_end
                continuous_focus_minutes = 0
                last_scheduled_end = break_end
                continue

            work_minutes = min(
                demand.remaining_minutes,
                available_minutes,
                remaining_before_break,
            )
            if work_minutes < 15:
                break

            block_end = cursor + timedelta(minutes=work_minutes)
            reason = f"Scheduled using {strategy.replace('_', ' ')} strategy."
            if work_minutes < demand.remaining_minutes:
                reason = f"Split task block using {strategy.replace('_', ' ')} strategy."

            items.append(
                PlannedItemDraft(
                    task_id=demand.task.id,
                    item_type=PlanItemType.TASK,
                    start_time=cursor,
                    end_time=block_end,
                    reason=reason,
                    status=PlanItemStatus.SCHEDULED,
                )
            )
            demand.remaining_minutes -= work_minutes
            cursor = block_end
            continuous_focus_minutes += work_minutes
            last_scheduled_end = block_end

            if demand.remaining_minutes <= 0:
                demand_index += 1

            remaining_after_block = int((slot_end - cursor).total_seconds() // 60)
            if (
                continuous_focus_minutes >= settings.default_focus_block_minutes
                and remaining_after_block >= settings.default_break_minutes
                and (
                    demand_index < len(demands)
                    or (demand.remaining_minutes > 0)
                )
            ):
                break_end = cursor + timedelta(minutes=settings.default_break_minutes)
                items.append(
                    PlannedItemDraft(
                        task_id=None,
                        item_type=PlanItemType.BREAK,
                        start_time=cursor,
                        end_time=break_end,
                        reason=f"{settings.default_break_minutes}-minute break after a focus block.",
                        status=PlanItemStatus.INFO,
                    )
                )
                cursor = break_end
                continuous_focus_minutes = 0
                last_scheduled_end = break_end

        if cursor < slot_end:
            continuous_focus_minutes = 0

    return items, demands


def compute_daily_plan_from_free_slots(
    session: Session,
    target_date: date,
    free_slot_result: FreeSlotResult,
) -> PlanComputation:
    tasks = _load_plannable_tasks(session, target_date)
    tasks_by_id = {task.id: task for task in tasks if task.id is not None}
    total_free_minutes = sum(slot.duration_minutes for slot in free_slot_result.free_slots)

    logs = [
        AgentLogDraft(
            agent_name="Calendar Agent",
            action="load_busy_blocks",
            input_summary=f"Read busy blocks for {target_date.isoformat()}.",
            output_summary=f"Loaded {len(free_slot_result.events)} calendar events.",
            status=AgentLogStatus.SUCCESS,
        ),
        AgentLogDraft(
            agent_name="Free-Time Agent",
            action="find_free_slots",
            input_summary=f"Computed availability for {target_date.isoformat()}.",
            output_summary=(
                f"Found {len(free_slot_result.free_slots)} free slots totalling "
                f"{total_free_minutes} minutes."
            ),
            status=AgentLogStatus.SUCCESS,
        ),
    ]

    strategies = ["deadline_first", "priority_first", "priority_compact"]
    final_items = []
    final_unscheduled: list[UnscheduledTaskRead] = []
    final_report = ValidationReport(valid=False, issues=[])
    retry_count = 0

    for attempt_index, strategy in enumerate(strategies, start=1):
        attempt_items, demands = _plan_with_strategy(tasks, free_slot_result.free_slots, strategy)
        unscheduled = _build_unscheduled_tasks(demands)
        logs.append(
            AgentLogDraft(
                agent_name="Planning Agent",
                action="generate_draft_plan",
                input_summary=(
                    f"Attempt {attempt_index} used {strategy.replace('_', ' ')} ordering "
                    f"for {len(tasks)} tasks."
                ),
                output_summary=(
                    f"Scheduled {sum(1 for item in attempt_items if item.task_id is not None)} "
                    f"blocks and left {len(unscheduled)} tasks with remaining time."
                ),
                status=AgentLogStatus.SUCCESS,
            )
        )

        report = validate_plan_items(
            target_date=target_date,
            items=attempt_items,
            tasks_by_id=tasks_by_id,
            busy_events=free_slot_result.events,
        )
        if report.valid:
            logs.append(
                AgentLogDraft(
                    agent_name="Validation Agent",
                    action="validate_plan",
                    input_summary=f"Validated attempt {attempt_index} for {target_date.isoformat()}.",
                    output_summary=f"Plan passed validation on attempt {attempt_index}.",
                    status=AgentLogStatus.SUCCESS,
                )
            )
            final_items = attempt_items
            final_unscheduled = unscheduled
            final_report = report
            retry_count = attempt_index - 1
            break

        issue_summary = "; ".join(issue.message for issue in report.issues[:2])
        logs.append(
            AgentLogDraft(
                agent_name="Validation Agent",
                action="validate_plan",
                input_summary=f"Validated attempt {attempt_index} for {target_date.isoformat()}.",
                output_summary=f"Plan failed validation: {issue_summary}",
                status=AgentLogStatus.WARNING,
            )
        )
        final_items = attempt_items
        final_unscheduled = unscheduled
        final_report = report
        retry_count = max(attempt_index - 1, 0)

    if final_report.valid:
        status = DailyPlanStatus.PARTIAL if final_unscheduled else DailyPlanStatus.VALIDATED
        validation_summary = "Validated successfully."
        if final_unscheduled:
            validation_summary = (
                f"Validated successfully with {len(final_unscheduled)} task(s) still needing time."
            )
    else:
        status = DailyPlanStatus.FAILED
        validation_summary = "; ".join(issue.message for issue in final_report.issues) or "Validation failed."

    return PlanComputation(
        items=final_items,
        unscheduled_tasks=final_unscheduled,
        logs=logs,
        status=status,
        retry_count=retry_count,
        validation_summary=validation_summary,
    )


def compute_daily_plan(session: Session, target_date: date) -> PlanComputation:
    free_slot_result = calculate_free_slots_for_date(session, target_date)
    return compute_daily_plan_from_free_slots(session, target_date, free_slot_result)


def save_daily_plan(
    session: Session,
    target_date: date,
    computation: PlanComputation,
) -> DailyPlan:
    settings = get_settings()
    plan = session.exec(
        select(DailyPlan).where(
            DailyPlan.user_id == settings.default_user_id,
            DailyPlan.plan_date == target_date,
        )
    ).first()

    if plan is None:
        plan = DailyPlan(user_id=settings.default_user_id, plan_date=target_date)
        session.add(plan)
        session.flush()
    else:
        existing_items = session.exec(
            select(DailyPlanItem).where(DailyPlanItem.plan_id == plan.id)
        ).all()
        for item in existing_items:
            session.delete(item)
        existing_logs = session.exec(
            select(AgentLog).where(AgentLog.plan_id == plan.id)
        ).all()
        for log in existing_logs:
            session.delete(log)
        session.flush()

    plan.status = computation.status
    plan.retry_count = computation.retry_count
    plan.validation_summary = computation.validation_summary
    session.add(plan)
    session.flush()

    for draft in computation.items:
        session.add(
            DailyPlanItem(
                plan_id=plan.id,
                task_id=draft.task_id,
                item_type=draft.item_type,
                start_time=draft.start_time,
                end_time=draft.end_time,
                reason=draft.reason,
                status=draft.status,
            )
        )

    for draft in computation.logs:
        session.add(
            AgentLog(
                plan_id=plan.id,
                context_date=target_date,
                agent_name=draft.agent_name,
                action=draft.action,
                input_summary=draft.input_summary,
                output_summary=draft.output_summary,
                status=draft.status,
            )
        )

    session.commit()
    session.refresh(plan)
    return plan


def _load_plan_items(session: Session, plan_id: int) -> list[DailyPlanItem]:
    return list(
        session.exec(
            select(DailyPlanItem)
            .where(DailyPlanItem.plan_id == plan_id)
            .order_by(DailyPlanItem.start_time.asc(), DailyPlanItem.end_time.asc())
        )
    )


def build_daily_plan_read(
    session: Session,
    plan: DailyPlan,
    unscheduled_override: list[UnscheduledTaskRead] | None = None,
) -> DailyPlanRead:
    items = _load_plan_items(session, plan.id)
    task_ids = [item.task_id for item in items if item.task_id is not None]
    tasks = list(session.exec(select(Task).where(Task.id.in_(task_ids)))) if task_ids else []
    tasks_by_id = {task.id: task for task in tasks if task.id is not None}

    item_reads: list[DailyPlanItemRead] = []
    scheduled_minutes_by_task: dict[int, int] = {}
    for item in items:
        duration_minutes = int((item.end_time - item.start_time).total_seconds() // 60)
        if item.task_id is not None:
            scheduled_minutes_by_task[item.task_id] = scheduled_minutes_by_task.get(item.task_id, 0) + duration_minutes
        item_reads.append(
            DailyPlanItemRead(
                id=item.id,
                task_id=item.task_id,
                task_title=tasks_by_id[item.task_id].title if item.task_id in tasks_by_id else None,
                item_type=item.item_type,
                start_time=item.start_time,
                end_time=item.end_time,
                duration_minutes=duration_minutes,
                reason=item.reason,
                status=item.status,
            )
        )

    if unscheduled_override is None:
        unscheduled_override = []
        for task in _load_plannable_tasks(session, plan.plan_date):
            if task.id is None:
                continue
            scheduled_minutes = scheduled_minutes_by_task.get(task.id, 0)
            remaining_minutes = max(task.estimated_minutes - scheduled_minutes, 0)
            if remaining_minutes > 0:
                reason = "Task still needs additional free time."
                if scheduled_minutes == 0:
                    reason = "Task was not scheduled in the saved plan."
                unscheduled_override.append(
                    UnscheduledTaskRead(
                        task_id=task.id,
                        title=task.title,
                        priority=task.priority,
                        remaining_minutes=remaining_minutes,
                        reason=reason,
                    )
                )

    return DailyPlanRead(
        id=plan.id,
        user_id=plan.user_id,
        plan_date=plan.plan_date,
        status=plan.status,
        retry_count=plan.retry_count,
        validation_summary=plan.validation_summary,
        created_at=plan.created_at,
        items=item_reads,
        unscheduled_tasks=unscheduled_override,
    )
