from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import get_settings
from app.models import AgentLog, CalendarEvent, DailyPlan, DailyPlanItem, Goal, Notification, Task, User


settings = get_settings()

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def seed_default_user() -> None:
    with Session(engine) as session:
        existing_user = session.exec(
            select(User).where(User.id == settings.default_user_id)
        ).first()
        if existing_user is not None:
            return

        user = User(
            id=settings.default_user_id,
            name=settings.default_user_name,
            email=settings.default_user_email,
        )
        session.add(user)
        session.commit()
