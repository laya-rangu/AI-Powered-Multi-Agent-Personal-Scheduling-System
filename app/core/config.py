import os
from dataclasses import dataclass
from datetime import time
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_time(name: str, default: str) -> time:
    raw = os.getenv(name, default).strip()
    try:
        return time.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid time value for {name}: {raw}") from exc


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    debug: bool
    database_url: str
    default_user_id: int
    default_user_name: str
    default_user_email: str
    default_workday_start: time
    default_workday_end: time
    default_focus_block_minutes: int
    default_break_minutes: int
    app_timezone: str
    morning_checkin_time: time
    enable_reminder_scheduler: bool
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: int


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "FocusFlow AI"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        debug=_read_bool("DEBUG", False),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./focusflow.db"),
        default_user_id=int(os.getenv("DEFAULT_USER_ID", "1")),
        default_user_name=os.getenv("DEFAULT_USER_NAME", "Local User"),
        default_user_email=os.getenv("DEFAULT_USER_EMAIL", "local-user@focusflow.dev"),
        default_workday_start=_read_time("DEFAULT_WORKDAY_START", "09:00"),
        default_workday_end=_read_time("DEFAULT_WORKDAY_END", "18:00"),
        default_focus_block_minutes=int(os.getenv("DEFAULT_FOCUS_BLOCK_MINUTES", "90")),
        default_break_minutes=int(os.getenv("DEFAULT_BREAK_MINUTES", "10")),
        app_timezone=os.getenv("APP_TIMEZONE", "America/New_York"),
        morning_checkin_time=_read_time("MORNING_CHECKIN_TIME", "08:00"),
        enable_reminder_scheduler=_read_bool("ENABLE_REMINDER_SCHEDULER", True),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b"),
        ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45")),
    )
