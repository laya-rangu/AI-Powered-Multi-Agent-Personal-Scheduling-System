from sqlmodel import Session

from app.models.entities import Goal, Task
from app.models.enums import GoalStatus, TaskStatus


def _task_contribution(task: Task | None) -> float:
    if task is None or task.goal_id is None or task.status != TaskStatus.COMPLETED:
        return 0.0
    return float(task.goal_progress_value)


def _apply_goal_delta(session: Session, goal_id: int | None, delta: float) -> None:
    if goal_id is None or delta == 0:
        return

    goal = session.get(Goal, goal_id)
    if goal is None:
        return

    goal.current_value = max(0.0, round(goal.current_value + delta, 4))
    if goal.current_value >= goal.target_value:
        goal.status = GoalStatus.COMPLETED
    elif goal.status == GoalStatus.COMPLETED and goal.current_value < goal.target_value:
        goal.status = GoalStatus.ACTIVE
    session.add(goal)


def sync_goal_progress_for_task_change(
    session: Session,
    before_task: Task | None,
    after_task: Task | None,
) -> None:
    _apply_goal_delta(
        session,
        before_task.goal_id if before_task is not None else None,
        -_task_contribution(before_task),
    )
    _apply_goal_delta(
        session,
        after_task.goal_id if after_task is not None else None,
        _task_contribution(after_task),
    )

