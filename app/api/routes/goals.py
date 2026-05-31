from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.api.deps import get_session
from app.core.config import get_settings
from app.models.entities import Goal, Task
from app.models.enums import GoalStatus, TaskStatus
from app.models.schemas import GoalCreate, GoalProgressSnapshot, GoalRead, GoalUpdate


router = APIRouter(prefix="/goals", tags=["goals"])
SessionDep = Annotated[Session, Depends(get_session)]


def _progress_percentage(goal: Goal) -> float:
    if goal.target_value <= 0:
        return 0.0
    return round(min((goal.current_value / goal.target_value) * 100, 100.0), 2)


def _sync_goal_status(goal: Goal) -> None:
    if goal.current_value >= goal.target_value:
        goal.status = GoalStatus.COMPLETED
    elif goal.status == GoalStatus.COMPLETED and goal.current_value < goal.target_value:
        goal.status = GoalStatus.ACTIVE


def _to_goal_read(goal: Goal) -> GoalRead:
    return GoalRead(**goal.model_dump(), progress_percentage=_progress_percentage(goal))


def _get_user_goal_or_404(session: Session, goal_id: int) -> Goal:
    settings = get_settings()
    goal = session.get(Goal, goal_id)
    if goal is None or goal.user_id != settings.default_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, session: SessionDep) -> GoalRead:
    settings = get_settings()
    goal = Goal.model_validate(payload, update={"user_id": settings.default_user_id})
    _sync_goal_status(goal)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return _to_goal_read(goal)


@router.get("", response_model=list[GoalRead])
def list_goals(session: SessionDep) -> list[GoalRead]:
    settings = get_settings()
    statement = (
        select(Goal)
        .where(Goal.user_id == settings.default_user_id)
        .order_by(Goal.created_at.desc())
    )
    goals = list(session.exec(statement))
    return [_to_goal_read(goal) for goal in goals]


@router.get("/progress", response_model=list[GoalProgressSnapshot])
def list_goal_progress(session: SessionDep) -> list[GoalProgressSnapshot]:
    settings = get_settings()
    statement = (
        select(Goal)
        .where(Goal.user_id == settings.default_user_id)
        .order_by(Goal.created_at.desc())
    )
    goals = list(session.exec(statement))
    snapshots: list[GoalProgressSnapshot] = []
    for goal in goals:
        completed_tasks = session.exec(
            select(Task).where(
                Task.goal_id == goal.id,
                Task.status == TaskStatus.COMPLETED,
                Task.user_id == settings.default_user_id,
            )
        ).all()
        snapshots.append(
            GoalProgressSnapshot(
                id=goal.id,
                title=goal.title,
                goal_type=goal.goal_type,
                status=goal.status,
                current_value=goal.current_value,
                target_value=goal.target_value,
                unit=goal.unit,
                linked_completed_tasks=len(completed_tasks),
                progress_percentage=_progress_percentage(goal),
            )
        )
    return snapshots


@router.get("/{goal_id}", response_model=GoalRead)
def get_goal(goal_id: int, session: SessionDep) -> GoalRead:
    return _to_goal_read(_get_user_goal_or_404(session, goal_id))


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(goal_id: int, payload: GoalUpdate, session: SessionDep) -> GoalRead:
    goal = _get_user_goal_or_404(session, goal_id)
    changes = payload.model_dump(exclude_unset=True)

    for field_name, value in changes.items():
        setattr(goal, field_name, value)

    _sync_goal_status(goal)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return _to_goal_read(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, session: SessionDep) -> Response:
    goal = _get_user_goal_or_404(session, goal_id)
    linked_task = session.exec(
        select(Task).where(Task.goal_id == goal.id, Task.user_id == goal.user_id)
    ).first()
    if linked_task is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Goal is linked to tasks. Unlink or delete those tasks first.",
        )

    session.delete(goal)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
