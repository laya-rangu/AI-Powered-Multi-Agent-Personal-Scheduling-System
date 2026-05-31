from dataclasses import dataclass
from datetime import date

from app.core.config import get_settings
from app.models.entities import CalendarEvent, Task
from app.models.enums import PlanItemType, TaskPriority
from app.services.free_slots import get_workday_bounds


@dataclass
class ValidationIssue:
    message: str


@dataclass
class ValidationReport:
    valid: bool
    issues: list[ValidationIssue]


def _priority_rank(priority: TaskPriority) -> int:
    return {
        TaskPriority.LOW: 0,
        TaskPriority.MEDIUM: 1,
        TaskPriority.HIGH: 2,
        TaskPriority.URGENT: 3,
    }[priority]


def validate_plan_items(
    target_date: date,
    items,
    tasks_by_id: dict[int, Task],
    busy_events: list[CalendarEvent],
) -> ValidationReport:
    settings = get_settings()
    issues: list[ValidationIssue] = []
    day_start, day_end = get_workday_bounds(target_date)
    ordered_items = sorted(items, key=lambda item: (item.start_time, item.end_time))

    previous_end = None
    continuous_focus_minutes = 0
    for item in ordered_items:
        if item.start_time >= item.end_time:
            issues.append(ValidationIssue(message="A plan item has an invalid time range."))
            continue

        if item.start_time < day_start or item.end_time > day_end:
            issues.append(ValidationIssue(message="A plan item falls outside working hours."))

        if previous_end is not None and item.start_time < previous_end:
            issues.append(ValidationIssue(message="Plan items overlap with each other."))

        for event in busy_events:
            if item.start_time < event.end_time and item.end_time > event.start_time:
                issues.append(
                    ValidationIssue(
                        message=f"Plan overlaps with calendar event '{event.title}'."
                    )
                )
                break

        if previous_end is None or item.start_time > previous_end:
            continuous_focus_minutes = 0

        duration_minutes = int((item.end_time - item.start_time).total_seconds() // 60)
        if item.item_type == PlanItemType.BREAK:
            continuous_focus_minutes = 0
        else:
            continuous_focus_minutes += duration_minutes
            if continuous_focus_minutes > settings.default_focus_block_minutes:
                issues.append(
                    ValidationIssue(
                        message="A focus streak exceeds the configured break threshold."
                    )
                )

        previous_end = item.end_time

    earliest_start_by_task: dict[int, object] = {}
    for item in ordered_items:
        if item.item_type != PlanItemType.TASK or item.task_id is None:
            continue
        earliest_start_by_task.setdefault(item.task_id, item.start_time)

    scheduled_tasks = [
        tasks_by_id[task_id]
        for task_id in earliest_start_by_task
        if task_id in tasks_by_id
    ]
    for high_task in scheduled_tasks:
        for lower_task in scheduled_tasks:
            if high_task.id == lower_task.id:
                continue
            if _priority_rank(high_task.priority) <= _priority_rank(lower_task.priority):
                continue

            high_start = earliest_start_by_task[high_task.id]
            lower_start = earliest_start_by_task[lower_task.id]
            if high_start <= lower_start:
                continue

            if (
                high_task.deadline is None
                or lower_task.deadline is None
                or high_task.deadline <= lower_task.deadline
            ):
                issues.append(
                    ValidationIssue(
                        message=(
                            f"Higher-priority task '{high_task.title}' should be scheduled "
                            f"before '{lower_task.title}'."
                        )
                    )
                )
                return ValidationReport(valid=False, issues=issues)

    return ValidationReport(valid=len(issues) == 0, issues=issues)

