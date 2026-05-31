from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.api.deps import get_session
from app.models.entities import AgentLog
from app.models.schemas import AgentLogRead


router = APIRouter(tags=["agent-logs"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/agent-logs", response_model=list[AgentLogRead])
def list_agent_logs(
    session: SessionDep,
    target_date: date | None = Query(default=None, alias="date"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AgentLog]:
    statement = select(AgentLog)

    if target_date is not None:
        statement = statement.where(AgentLog.context_date == target_date).order_by(AgentLog.id.asc())
    else:
        statement = statement.order_by(AgentLog.created_at.desc())

    return list(session.exec(statement.limit(limit)))
