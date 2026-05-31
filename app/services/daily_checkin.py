from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime

import httpx
from sqlmodel import Session

from app.core.config import get_settings
from app.models.entities import AgentLog, Task
from app.models.enums import AgentLogStatus, ExtractionSource, TaskPriority, TaskStatus
from app.models.schemas import DailyCheckInResponse, ExtractedTaskCandidate, TaskRead
from app.services.notifications import mark_morning_checkin_complete_for_date


class OllamaServiceError(Exception):
    """Raised when the Ollama extraction call fails."""


@dataclass
class ExtractionResult:
    model: str
    source: ExtractionSource
    tasks: list[ExtractedTaskCandidate]
    warnings: list[str]


@dataclass
class CheckInProcessingResult:
    response: DailyCheckInResponse
    created_tasks: list[TaskRead]


def _build_prompt(message: str, target_date: date) -> str:
    return f"""
You extract structured daily tasks from a user's natural-language morning check-in.

Today is {target_date.isoformat()}.

Return only valid JSON with this exact shape:
{{
  "tasks": [
    {{
      "title": "string",
      "description": "string or null",
      "priority": "low|medium|high|urgent",
      "estimated_minutes": 15-480 integer,
      "deadline": "ISO 8601 datetime string or null"
    }}
  ]
}}

Rules:
- Split combined requests into separate actionable tasks.
- Keep titles short and clear.
- Use null when no deadline is mentioned.
- Infer sensible priorities and durations.
- Do not include reasoning, thinking, or markdown.
- Never include extra keys.
- Output JSON only.

User check-in:
{message}
""".strip()


def _extract_json_object(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize_tasks(payload: dict) -> list[ExtractedTaskCandidate]:
    raw_tasks = payload.get("tasks", [])
    if not isinstance(raw_tasks, list):
        raise ValueError("The model response did not contain a task list.")

    tasks: list[ExtractedTaskCandidate] = []
    for raw_task in raw_tasks:
        try:
            task = ExtractedTaskCandidate.model_validate(raw_task)
        except Exception:
            continue
        tasks.append(task)
    return tasks


def extract_tasks_with_ollama(message: str, target_date: date, model: str) -> list[ExtractedTaskCandidate]:
    settings = get_settings()
    payload = {
        "model": model,
        "prompt": _build_prompt(message, target_date),
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 220},
    }
    try:
        with httpx.Client(timeout=settings.ollama_timeout_seconds) as client:
            response = client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaServiceError(f"Ollama request failed: {exc}") from exc

    body = response.json()
    raw_content = body.get("response", "")
    if not raw_content:
        raise OllamaServiceError("Ollama returned an empty response.")

    try:
        parsed = _extract_json_object(raw_content)
        tasks = _normalize_tasks(parsed)
    except Exception as exc:
        raise OllamaServiceError("Ollama returned malformed task JSON.") from exc

    if not tasks:
        raise OllamaServiceError("Ollama did not extract any usable tasks.")
    return tasks


def _clean_segment(segment: str) -> str:
    text = segment.strip()
    text = re.sub(r"^[\-\*\u2022\d\.\)\s]+", "", text)
    text = re.sub(r"^(i need to|need to|please|today i need to)\s+", "", text, flags=re.IGNORECASE)
    return text.strip(" .")


def _infer_priority(text: str) -> TaskPriority:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ["urgent", "asap", "immediately", "right away"]):
        return TaskPriority.URGENT
    if any(keyword in lowered for keyword in ["important", "high priority", "deadline", "submit today"]):
        return TaskPriority.HIGH
    if any(keyword in lowered for keyword in ["later", "optional", "if possible"]):
        return TaskPriority.LOW
    return TaskPriority.MEDIUM


def _infer_estimated_minutes(text: str) -> int:
    lowered = text.lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|hr)\b", lowered)
    if match:
        return max(15, min(int(float(match.group(1)) * 60), 480))

    match = re.search(r"(\d+)\s*(minutes?|mins?|min)\b", lowered)
    if match:
        return max(15, min(int(match.group(1)), 480))

    if "email" in lowered or "reply" in lowered:
        return 30
    if "study" in lowered or "prepare" in lowered or "project" in lowered:
        return 90
    return 45


def _split_message_into_segments(message: str) -> list[str]:
    if re.search(r"[\n\r]", message):
        parts = re.split(r"[\r\n]+", message)
    elif ";" in message:
        parts = message.split(";")
    else:
        parts = re.split(
            r"(?:,\s+|\s+and\s+)(?=(?:finish|complete|send|study|work|prepare|review|call|email|apply|practice|write|update|submit)\b)",
            message,
            flags=re.IGNORECASE,
        )

    segments = [_clean_segment(part) for part in parts]
    return [segment for segment in segments if segment]


def fallback_extract_tasks(message: str) -> list[ExtractedTaskCandidate]:
    segments = _split_message_into_segments(message)
    if not segments:
        segments = [_clean_segment(message)]

    tasks: list[ExtractedTaskCandidate] = []
    for segment in segments:
        if not segment:
            continue
        task = ExtractedTaskCandidate(
            title=segment[:200],
            description=None,
            priority=_infer_priority(segment),
            estimated_minutes=_infer_estimated_minutes(segment),
            deadline=None,
        )
        tasks.append(task)

    if not tasks:
        tasks.append(
            ExtractedTaskCandidate(
                title=message.strip()[:200],
                description=None,
                priority=TaskPriority.MEDIUM,
                estimated_minutes=45,
                deadline=None,
            )
        )
    return tasks


def extract_tasks_from_message(message: str, target_date: date, model: str | None = None) -> ExtractionResult:
    settings = get_settings()
    selected_model = model or settings.ollama_model

    try:
        tasks = extract_tasks_with_ollama(message, target_date, selected_model)
        return ExtractionResult(
            model=selected_model,
            source=ExtractionSource.OLLAMA,
            tasks=tasks,
            warnings=[],
        )
    except OllamaServiceError as exc:
        fallback_tasks = fallback_extract_tasks(message)
        return ExtractionResult(
            model=selected_model,
            source=ExtractionSource.FALLBACK,
            tasks=fallback_tasks,
            warnings=[str(exc), "Used heuristic fallback extraction instead."],
        )


def run_daily_checkin(
    session: Session,
    *,
    message: str,
    target_date: date,
    persist_tasks: bool = True,
    model: str | None = None,
) -> CheckInProcessingResult:
    settings = get_settings()
    extraction = extract_tasks_from_message(message, target_date, model)

    created_task_models: list[Task] = []
    if persist_tasks:
        for candidate in extraction.tasks:
            task = Task(
                user_id=settings.default_user_id,
                title=candidate.title,
                description=candidate.description,
                priority=candidate.priority,
                deadline=candidate.deadline,
                estimated_minutes=candidate.estimated_minutes,
                status=TaskStatus.PENDING,
            )
            session.add(task)
            created_task_models.append(task)

        session.flush()

    log_status = AgentLogStatus.SUCCESS
    if extraction.source == ExtractionSource.FALLBACK:
        log_status = AgentLogStatus.WARNING

    session.add(
        AgentLog(
            context_date=target_date,
            agent_name="Daily Agent",
            action="extract_tasks_from_checkin",
            input_summary=f"Processed daily check-in for {target_date.isoformat()}.",
            output_summary=(
                f"Extracted {len(extraction.tasks)} tasks using {extraction.source.value} "
                f"with model {extraction.model}."
            ),
            status=log_status,
        )
    )

    mark_morning_checkin_complete_for_date(session, target_date)
    session.commit()

    created_tasks: list[TaskRead] = []
    for task in created_task_models:
        session.refresh(task)
        created_tasks.append(TaskRead.model_validate(task))

    response = DailyCheckInResponse(
        date=target_date,
        model=extraction.model,
        source=extraction.source,
        used_fallback=extraction.source == ExtractionSource.FALLBACK,
        extracted_tasks=extraction.tasks,
        created_tasks=created_tasks,
        warnings=extraction.warnings,
    )
    return CheckInProcessingResult(response=response, created_tasks=created_tasks)
