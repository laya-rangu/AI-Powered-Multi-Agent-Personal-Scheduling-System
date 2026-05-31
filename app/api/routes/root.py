from fastapi import APIRouter

from app.core.config import get_settings


router = APIRouter(tags=["system"])


@router.get("/")
def read_root() -> dict[str, object]:
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "ok",
        "iteration": {
            "completed": [0, 1, 2, 3, 4, 5, 6, 7],
            "current_focus": 8,
            "next": "Frontend dashboard",
        },
        "defaults": {
            "workday_start": settings.default_workday_start.isoformat(timespec="minutes"),
            "workday_end": settings.default_workday_end.isoformat(timespec="minutes"),
            "focus_block_minutes": settings.default_focus_block_minutes,
            "break_minutes": settings.default_break_minutes,
            "timezone": settings.app_timezone,
            "morning_checkin_time": settings.morning_checkin_time.isoformat(timespec="minutes"),
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
        },
    }
