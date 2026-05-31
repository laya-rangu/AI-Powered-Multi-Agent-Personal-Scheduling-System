from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_session
from app.models.enums import NotificationStatus
from app.models.schemas import NotificationRead, NotificationUpdate
from app.services.notifications import get_notification_or_none, list_notifications


router = APIRouter(prefix="/notifications", tags=["notifications"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[NotificationRead])
def get_notifications(
    session: SessionDep,
    status: NotificationStatus | None = None,
) -> list[NotificationRead]:
    notifications = list_notifications(session, status_filter=status)
    return [NotificationRead.model_validate(notification) for notification in notifications]


@router.patch("/{notification_id}", response_model=NotificationRead)
def update_notification(
    notification_id: int,
    payload: NotificationUpdate,
    session: SessionDep,
) -> NotificationRead:
    notification = get_notification_or_none(session, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.status = payload.status
    if payload.status == NotificationStatus.READ:
        from datetime import datetime, timezone

        notification.read_at = datetime.now(timezone.utc)
    else:
        notification.read_at = None

    session.add(notification)
    session.commit()
    session.refresh(notification)
    return NotificationRead.model_validate(notification)

