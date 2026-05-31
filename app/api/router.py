from fastapi import APIRouter

from app.api.routes.agent_logs import router as agent_logs_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.calendar import router as calendar_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.daily import router as daily_router
from app.api.routes.goals import router as goals_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.root import router as root_router
from app.api.routes.tasks import router as tasks_router


api_router = APIRouter()
api_router.include_router(root_router)
api_router.include_router(tasks_router)
api_router.include_router(goals_router)
api_router.include_router(calendar_router)
api_router.include_router(daily_router)
api_router.include_router(agent_logs_router)
api_router.include_router(assistant_router)
api_router.include_router(notifications_router)
api_router.include_router(dashboard_router)
