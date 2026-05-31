from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session, select

from app.api.deps import get_session
from app.core.config import get_settings
from app.models.entities import Goal, Task
from app.models.enums import TaskPriority, TaskStatus
from app.models.schemas import TaskCreate, TaskRead, TaskUpdate
from app.services.goal_progress import sync_goal_progress_for_task_change


router = APIRouter(prefix="/tasks", tags=["tasks"])
SessionDep = Annotated[Session, Depends(get_session)]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_user_task_or_404(session: Session, task_id: int) -> Task:
    settings = get_settings()
    task = session.get(Task, task_id)
    if task is None or task.user_id != settings.default_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _validate_goal(session: Session, goal_id: int | None) -> None:
    settings = get_settings()
    if goal_id is None:
        return

    goal = session.get(Goal, goal_id)
    if goal is None or goal.user_id != settings.default_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked goal not found")


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, session: SessionDep) -> Task:
    settings = get_settings()
    _validate_goal(session, payload.goal_id)

    task = Task.model_validate(payload, update={"user_id": settings.default_user_id})
    if task.status == TaskStatus.COMPLETED:
        task.completed_at = _utc_now()

    session.add(task)
    session.flush()
    sync_goal_progress_for_task_change(session, None, task)
    session.commit()
    session.refresh(task)
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(
    session: SessionDep,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: TaskPriority | None = None,
    goal_id: int | None = None,
) -> list[Task]:
    settings = get_settings()
    statement = select(Task).where(Task.user_id == settings.default_user_id)

    if status_filter is not None:
        statement = statement.where(Task.status == status_filter)
    if priority is not None:
        statement = statement.where(Task.priority == priority)
    if goal_id is not None:
        statement = statement.where(Task.goal_id == goal_id)

    statement = statement.order_by(Task.created_at.desc())
    return list(session.exec(statement))


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, session: SessionDep) -> Task:
    return _get_user_task_or_404(session, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, session: SessionDep) -> Task:
    task = _get_user_task_or_404(session, task_id)
    before_task = Task.model_validate(task.model_dump())

    changes = payload.model_dump(exclude_unset=True)
    if "goal_id" in changes:
        _validate_goal(session, changes["goal_id"])

    for field_name, value in changes.items():
        setattr(task, field_name, value)

    if task.status == TaskStatus.COMPLETED and before_task.status != TaskStatus.COMPLETED:
        task.completed_at = _utc_now()
    elif task.status != TaskStatus.COMPLETED and before_task.status == TaskStatus.COMPLETED:
        task.completed_at = None

    sync_goal_progress_for_task_change(session, before_task, task)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: SessionDep) -> Response:
    task = _get_user_task_or_404(session, task_id)
    sync_goal_progress_for_task_change(session, task, None)
    session.delete(task)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
