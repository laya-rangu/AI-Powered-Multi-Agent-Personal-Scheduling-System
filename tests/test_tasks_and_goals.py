from datetime import date, timedelta

from app.models.schemas import ExtractedTaskCandidate
from app.services import daily_checkin as daily_checkin_service
from app.services.daily_checkin import OllamaServiceError


def test_root_endpoint_reports_iterations(client):
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["iteration"]["completed"] == [0, 1, 2, 3, 4, 5, 6, 7]


def test_create_and_list_task(client):
    create_response = client.post(
        "/tasks",
        json={
            "title": "Prepare internship application",
            "priority": "high",
            "estimated_minutes": 60,
            "goal_progress_value": 0,
        },
    )
    assert create_response.status_code == 201
    created_task = create_response.json()
    assert created_task["title"] == "Prepare internship application"
    assert created_task["priority"] == "high"

    list_response = client.get("/tasks")
    assert list_response.status_code == 200
    tasks = list_response.json()
    assert len(tasks) == 1
    assert tasks[0]["id"] == created_task["id"]


def test_goal_progress_updates_when_task_completion_changes(client):
    goal_response = client.post(
        "/goals",
        json={
            "title": "Submit five strong applications",
            "goal_type": "weekly",
            "target_value": 5,
            "current_value": 0,
            "unit": "applications",
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=7)),
        },
    )
    assert goal_response.status_code == 201
    goal = goal_response.json()

    task_response = client.post(
        "/tasks",
        json={
            "title": "Apply to Company A",
            "priority": "urgent",
            "estimated_minutes": 45,
            "goal_id": goal["id"],
            "goal_progress_value": 2,
        },
    )
    assert task_response.status_code == 201
    task = task_response.json()

    complete_response = client.patch(
        f"/tasks/{task['id']}",
        json={"status": "completed"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["completed_at"] is not None

    progress_response = client.get("/goals/progress")
    assert progress_response.status_code == 200
    progress = progress_response.json()
    assert progress[0]["current_value"] == 2
    assert progress[0]["linked_completed_tasks"] == 1
    assert progress[0]["progress_percentage"] == 40.0

    reopen_response = client.patch(
        f"/tasks/{task['id']}",
        json={"status": "pending"},
    )
    assert reopen_response.status_code == 200
    assert reopen_response.json()["completed_at"] is None

    goal_detail = client.get(f"/goals/{goal['id']}")
    assert goal_detail.status_code == 200
    assert goal_detail.json()["current_value"] == 0
    assert goal_detail.json()["progress_percentage"] == 0


def test_calendar_events_and_free_slots(client):
    event_payloads = [
        {
            "title": "Morning standup",
            "start_time": "2026-06-01T10:00:00",
            "end_time": "2026-06-01T10:30:00",
            "source": "mock",
        },
        {
            "title": "Interview prep session",
            "start_time": "2026-06-01T13:00:00",
            "end_time": "2026-06-01T14:30:00",
            "source": "mock",
        },
    ]

    for payload in event_payloads:
        response = client.post("/calendar/events", json=payload)
        assert response.status_code == 201

    events_response = client.get("/calendar/events", params={"date": "2026-06-01"})
    assert events_response.status_code == 200
    assert len(events_response.json()) == 2

    free_slots_response = client.get("/calendar/free-slots", params={"date": "2026-06-01"})
    assert free_slots_response.status_code == 200
    free_slots = free_slots_response.json()

    assert free_slots == [
        {
            "start_time": "2026-06-01T09:00:00",
            "end_time": "2026-06-01T10:00:00",
            "duration_minutes": 60,
        },
        {
            "start_time": "2026-06-01T10:30:00",
            "end_time": "2026-06-01T13:00:00",
            "duration_minutes": 150,
        },
        {
            "start_time": "2026-06-01T14:30:00",
            "end_time": "2026-06-01T18:00:00",
            "duration_minutes": 210,
        },
    ]


def test_generate_daily_plan_with_break_insertion(client):
    client.post(
        "/tasks",
        json={
            "title": "Deep project work",
            "priority": "urgent",
            "estimated_minutes": 120,
            "goal_progress_value": 0,
        },
    )
    client.post(
        "/tasks",
        json={
            "title": "Follow-up applications",
            "priority": "medium",
            "estimated_minutes": 60,
            "goal_progress_value": 0,
        },
    )

    response = client.post("/daily/plan", json={"date": "2026-06-03"})
    assert response.status_code == 201
    plan = response.json()

    assert plan["status"] == "validated"
    assert plan["retry_count"] == 0
    assert any(item["item_type"] == "break" for item in plan["items"])
    assert plan["items"][0]["task_title"] == "Deep project work"
    assert plan["items"][1]["item_type"] == "break"
    assert plan["items"][1]["duration_minutes"] == 10

    saved_plan = client.get("/daily/plan", params={"date": "2026-06-03"})
    assert saved_plan.status_code == 200
    assert saved_plan.json()["id"] == plan["id"]


def test_daily_plan_validation_retries_and_logs(client):
    client.post(
        "/tasks",
        json={
            "title": "Deadline prep",
            "priority": "medium",
            "estimated_minutes": 120,
            "deadline": "2026-06-04T18:00:00",
            "goal_progress_value": 0,
        },
    )
    client.post(
        "/tasks",
        json={
            "title": "Urgent outreach",
            "priority": "urgent",
            "estimated_minutes": 30,
            "goal_progress_value": 0,
        },
    )

    response = client.post("/daily/plan", json={"date": "2026-06-04"})
    assert response.status_code == 201
    plan = response.json()

    assert plan["retry_count"] == 1
    first_task_block = next(item for item in plan["items"] if item["item_type"] == "task")
    assert first_task_block["task_title"] == "Urgent outreach"
    assert plan["validation_summary"] == "Validated successfully."

    logs_response = client.get("/agent-logs", params={"date": "2026-06-04"})
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert any(log["status"] == "warning" for log in logs)
    assert any(
        log["agent_name"] == "Validation Agent" and log["status"] == "success"
        for log in logs
    )


def test_daily_checkin_creates_tasks_from_ollama_extraction(client, monkeypatch):
    def fake_extract_with_ollama(message, target_date, model):
        return [
            ExtractedTaskCandidate(
                title="Finish portfolio update",
                description="Refresh the featured projects section.",
                priority="high",
                estimated_minutes=90,
                deadline="2026-06-05T20:00:00",
            ),
            ExtractedTaskCandidate(
                title="Send recruiter follow-up email",
                description=None,
                priority="medium",
                estimated_minutes=30,
                deadline=None,
            ),
        ]

    monkeypatch.setattr(daily_checkin_service, "extract_tasks_with_ollama", fake_extract_with_ollama)

    response = client.post(
        "/daily/checkin",
        json={
            "date": "2026-06-05",
            "message": "Today I need to finish my portfolio update and send a recruiter follow-up email.",
        },
    )
    assert response.status_code == 201
    payload = response.json()

    assert payload["source"] == "ollama"
    assert payload["used_fallback"] is False
    assert len(payload["extracted_tasks"]) == 2
    assert len(payload["created_tasks"]) == 2
    assert payload["created_tasks"][0]["title"] == "Finish portfolio update"

    tasks = client.get("/tasks").json()
    assert len(tasks) == 2

    logs = client.get("/agent-logs", params={"date": "2026-06-05"}).json()
    assert any(log["agent_name"] == "Daily Agent" and log["status"] == "success" for log in logs)


def test_daily_checkin_uses_fallback_when_ollama_fails(client, monkeypatch):
    def broken_extract(*args, **kwargs):
        raise OllamaServiceError("Ollama request failed: test failure")

    monkeypatch.setattr(daily_checkin_service, "extract_tasks_with_ollama", broken_extract)

    response = client.post(
        "/daily/checkin",
        json={
            "date": "2026-06-06",
            "message": "Urgent: finish resume in 2 hours and send recruiter email in 30 minutes",
        },
    )
    assert response.status_code == 201
    payload = response.json()

    assert payload["source"] == "fallback"
    assert payload["used_fallback"] is True
    assert len(payload["created_tasks"]) == 2
    assert payload["created_tasks"][0]["estimated_minutes"] == 120
    assert payload["created_tasks"][1]["estimated_minutes"] == 30
    assert len(payload["warnings"]) == 2

    logs = client.get("/agent-logs", params={"date": "2026-06-06"}).json()
    assert any(log["agent_name"] == "Daily Agent" and log["status"] == "warning" for log in logs)


def test_assistant_daily_plan_workflow_runs_through_langgraph(client, monkeypatch):
    def fake_extract_with_ollama(message, target_date, model):
        return [
            ExtractedTaskCandidate(
                title="Prepare interview answers",
                description=None,
                priority="urgent",
                estimated_minutes=90,
                deadline=None,
            ),
            ExtractedTaskCandidate(
                title="Send follow-up note",
                description=None,
                priority="medium",
                estimated_minutes=30,
                deadline=None,
            ),
        ]

    monkeypatch.setattr(daily_checkin_service, "extract_tasks_with_ollama", fake_extract_with_ollama)

    calendar_response = client.post(
        "/calendar/events",
        json={
            "title": "Class block",
            "start_time": "2026-06-08T10:00:00",
            "end_time": "2026-06-08T11:00:00",
            "source": "mock",
        },
    )
    assert calendar_response.status_code == 201

    response = client.post(
        "/assistant/daily-plan",
        json={
            "date": "2026-06-08",
            "message": "I need to prepare interview answers and send a follow-up note today.",
        },
    )
    assert response.status_code == 201
    payload = response.json()

    assert payload["source"] == "ollama"
    assert payload["used_fallback"] is False
    assert len(payload["created_tasks"]) == 2
    assert payload["daily_plan"]["status"] in {"validated", "partial"}
    assert [step["node_name"] for step in payload["workflow_steps"]] == [
        "daily_agent",
        "calendar_agent",
        "free_time_agent",
        "planning_agent",
        "validation_agent",
    ]
    assert payload["workflow_steps"][1]["agent_name"] == "Calendar Agent"
    assert payload["daily_plan"]["items"][0]["task_title"] == "Prepare interview answers"


def test_dashboard_today_shows_morning_checkin_prompt(client):
    response = client.get("/dashboard/today")
    assert response.status_code == 200
    payload = response.json()

    assert payload["morning_checkin_prompt"] is not None
    assert payload["morning_checkin_prompt"]["notification_type"] == "morning_checkin"
    assert payload["unread_notifications_count"] >= 1


def test_notifications_can_be_marked_read(client):
    notifications_response = client.get("/notifications")
    assert notifications_response.status_code == 200
    notification = notifications_response.json()[0]

    update_response = client.patch(
        f"/notifications/{notification['id']}",
        json={"status": "read"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "read"
    assert updated["read_at"] is not None


def test_daily_checkin_marks_today_prompt_as_read(client, monkeypatch):
    def fake_extract_with_ollama(message, target_date, model):
        return [
            ExtractedTaskCandidate(
                title="Finish coursework review",
                description=None,
                priority="medium",
                estimated_minutes=60,
                deadline=None,
            )
        ]

    monkeypatch.setattr(daily_checkin_service, "extract_tasks_with_ollama", fake_extract_with_ollama)

    before = client.get("/dashboard/today").json()
    assert before["morning_checkin_prompt"] is not None

    checkin_response = client.post(
        "/daily/checkin",
        json={
            "message": "Finish coursework review today.",
        },
    )
    assert checkin_response.status_code == 201

    after = client.get("/dashboard/today").json()
    assert after["morning_checkin_prompt"] is None
