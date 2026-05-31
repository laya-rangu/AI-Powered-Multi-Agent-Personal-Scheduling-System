from enum import Enum


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class GoalType(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"


class DailyPlanStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PARTIAL = "partial"
    FAILED = "failed"


class PlanItemType(str, Enum):
    TASK = "task"
    BREAK = "break"


class PlanItemStatus(str, Enum):
    SCHEDULED = "scheduled"
    INFO = "info"


class AgentLogStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ExtractionSource(str, Enum):
    OLLAMA = "ollama"
    FALLBACK = "fallback"


class NotificationType(str, Enum):
    MORNING_CHECKIN = "morning_checkin"
    SYSTEM = "system"


class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
