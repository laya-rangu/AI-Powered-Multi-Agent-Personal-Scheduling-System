from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from sqlmodel import Session
from typing_extensions import TypedDict

from app.models.enums import AgentLogStatus, ExtractionSource
from app.models.schemas import (
    AssistantDailyPlanRequest,
    AssistantDailyPlanResponse,
    DailyPlanRead,
    ExtractedTaskCandidate,
    TaskRead,
    WorkflowStepRead,
)
from app.services.daily_checkin import run_daily_checkin
from app.services.daily_planner import (
    build_daily_plan_read,
    compute_daily_plan_from_free_slots,
    save_daily_plan,
)
from app.services.free_slots import FreeSlotResult, calculate_free_slots_for_date, load_calendar_events_for_date


@dataclass(frozen=True)
class AssistantWorkflowContext:
    session: Session


class AssistantWorkflowState(TypedDict, total=False):
    message: str
    target_date: date
    model: str | None
    model_used: str
    source: ExtractionSource
    used_fallback: bool
    warnings: list[str]
    extracted_tasks: list[ExtractedTaskCandidate]
    created_tasks: list[TaskRead]
    busy_event_count: int
    free_slot_count: int
    free_minutes_total: int
    free_slot_result: FreeSlotResult
    daily_plan: DailyPlanRead
    workflow_steps: list[WorkflowStepRead]


def _append_step(
    state: AssistantWorkflowState,
    *,
    node_name: str,
    agent_name: str,
    summary: str,
    status: AgentLogStatus = AgentLogStatus.SUCCESS,
) -> list[WorkflowStepRead]:
    return state.get("workflow_steps", []) + [
        WorkflowStepRead(
            node_name=node_name,
            agent_name=agent_name,
            summary=summary,
            status=status,
        )
    ]


def _daily_agent_node(
    state: AssistantWorkflowState,
    runtime: Runtime[AssistantWorkflowContext],
) -> AssistantWorkflowState:
    result = run_daily_checkin(
        runtime.context.session,
        message=state["message"],
        target_date=state["target_date"],
        persist_tasks=True,
        model=state.get("model"),
    )
    return {
        "model_used": result.response.model,
        "source": result.response.source,
        "used_fallback": result.response.used_fallback,
        "warnings": result.response.warnings,
        "extracted_tasks": result.response.extracted_tasks,
        "created_tasks": result.response.created_tasks,
        "workflow_steps": _append_step(
            state,
            node_name="daily_agent",
            agent_name="Daily Agent",
            summary=(
                f"Extracted {len(result.response.extracted_tasks)} tasks using "
                f"{result.response.source.value}."
            ),
            status=AgentLogStatus.WARNING if result.response.used_fallback else AgentLogStatus.SUCCESS,
        ),
    }


def _calendar_agent_node(
    state: AssistantWorkflowState,
    runtime: Runtime[AssistantWorkflowContext],
) -> AssistantWorkflowState:
    events = load_calendar_events_for_date(runtime.context.session, state["target_date"])
    return {
        "busy_event_count": len(events),
        "workflow_steps": _append_step(
            state,
            node_name="calendar_agent",
            agent_name="Calendar Agent",
            summary=f"Loaded {len(events)} busy calendar blocks for the day.",
        ),
    }


def _free_time_agent_node(
    state: AssistantWorkflowState,
    runtime: Runtime[AssistantWorkflowContext],
) -> AssistantWorkflowState:
    free_slot_result = calculate_free_slots_for_date(runtime.context.session, state["target_date"])
    total_minutes = sum(slot.duration_minutes for slot in free_slot_result.free_slots)
    return {
        "free_slot_result": free_slot_result,
        "free_slot_count": len(free_slot_result.free_slots),
        "free_minutes_total": total_minutes,
        "workflow_steps": _append_step(
            state,
            node_name="free_time_agent",
            agent_name="Free-Time Agent",
            summary=(
                f"Found {len(free_slot_result.free_slots)} free slots totalling "
                f"{total_minutes} minutes."
            ),
        ),
    }


def _planning_agent_node(
    state: AssistantWorkflowState,
    runtime: Runtime[AssistantWorkflowContext],
) -> AssistantWorkflowState:
    computation = compute_daily_plan_from_free_slots(
        runtime.context.session,
        state["target_date"],
        state["free_slot_result"],
    )
    plan = save_daily_plan(runtime.context.session, state["target_date"], computation)
    plan_read = build_daily_plan_read(
        runtime.context.session,
        plan,
        unscheduled_override=computation.unscheduled_tasks,
    )
    return {
        "daily_plan": plan_read,
        "workflow_steps": _append_step(
            state,
            node_name="planning_agent",
            agent_name="Planning Agent",
            summary=(
                f"Generated a {plan_read.status.value} plan with "
                f"{len(plan_read.items)} items."
            ),
        ),
    }


def _validation_agent_node(
    state: AssistantWorkflowState,
    runtime: Runtime[AssistantWorkflowContext],
) -> AssistantWorkflowState:
    plan = state["daily_plan"]
    summary = plan.validation_summary or "Validation completed."
    if plan.retry_count:
        summary = f"{summary} Planner retried {plan.retry_count} time(s)."
    status = AgentLogStatus.SUCCESS if plan.status.value != "failed" else AgentLogStatus.ERROR
    return {
        "workflow_steps": _append_step(
            state,
            node_name="validation_agent",
            agent_name="Validation Agent",
            summary=summary,
            status=status,
        )
    }


@lru_cache
def build_assistant_daily_plan_graph():
    graph = StateGraph(
        state_schema=AssistantWorkflowState,
        context_schema=AssistantWorkflowContext,
    )
    graph.add_node("daily_agent", _daily_agent_node)
    graph.add_node("calendar_agent", _calendar_agent_node)
    graph.add_node("free_time_agent", _free_time_agent_node)
    graph.add_node("planning_agent", _planning_agent_node)
    graph.add_node("validation_agent", _validation_agent_node)

    graph.add_edge(START, "daily_agent")
    graph.add_edge("daily_agent", "calendar_agent")
    graph.add_edge("calendar_agent", "free_time_agent")
    graph.add_edge("free_time_agent", "planning_agent")
    graph.add_edge("planning_agent", "validation_agent")
    graph.add_edge("validation_agent", END)

    return graph.compile(name="focusflow-assistant-daily-plan")


def run_assistant_daily_plan_workflow(
    session: Session,
    payload: AssistantDailyPlanRequest,
) -> AssistantDailyPlanResponse:
    graph = build_assistant_daily_plan_graph()
    final_state = graph.invoke(
        {
            "message": payload.message,
            "target_date": payload.target_date,
            "model": payload.model,
            "workflow_steps": [],
        },
        context=AssistantWorkflowContext(session=session),
    )

    return AssistantDailyPlanResponse(
        date=payload.target_date,
        model=final_state["model_used"],
        source=final_state["source"],
        used_fallback=final_state["used_fallback"],
        warnings=final_state.get("warnings", []),
        extracted_tasks=final_state.get("extracted_tasks", []),
        created_tasks=final_state.get("created_tasks", []),
        daily_plan=final_state["daily_plan"],
        workflow_steps=final_state.get("workflow_steps", []),
    )
