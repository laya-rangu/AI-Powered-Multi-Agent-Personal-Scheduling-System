from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.api.router import api_router
from app.core.config import get_settings
from app.db import create_db_and_tables, engine, seed_default_user
from app.services.notifications import current_local_date, ensure_morning_checkin_notification_for_date
from app.services.reminders import reminder_scheduler


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    seed_default_user()
    with Session(engine) as session:
        ensure_morning_checkin_notification_for_date(session, current_local_date())
    reminder_scheduler.start()
    try:
        yield
    finally:
        reminder_scheduler.shutdown()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "FocusFlow AI is a local-first productivity assistant for tasks, goals, "
        "and daily planning."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
