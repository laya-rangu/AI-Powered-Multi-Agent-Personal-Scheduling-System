# FocusFlow AI

FocusFlow AI is a single-user, local-first productivity assistant that turns daily tasks, goals, and calendar availability into a structured daily plan.

This first implementation pass covers:

- Iteration 0: project setup, FastAPI app, SQLite connection, configuration, and Swagger docs
- Iteration 1: task CRUD, goal CRUD, and custom goal-progress updates driven by task completion
- Iteration 2: mock calendar events and free-slot detection
- Iteration 3: daily plan generation with task splitting and break insertion
- Iteration 4: validation, retry-based self-correction, and agent logs
- Iteration 5: Ollama-powered daily check-in and natural-language task extraction
- Iteration 6: LangGraph supervisor workflow and single end-to-end assistant endpoint
- Iteration 7: APScheduler morning reminders, notifications, and dashboard summary endpoint
- Iteration 8: React dashboard for check-ins, plans, tasks, goals, reminders, and agent logs

## Tech Stack

- FastAPI
- LangGraph
- LangChain
- SQLModel
- SQLite
- Uvicorn
- React
- Vite
- Tailwind CSS
- Recharts

## Sensible MVP Defaults

- Single local user only
- Daily scheduling planned for every day of the week
- Priority levels: `low`, `medium`, `high`, `urgent`
- Working hours: `09:00` to `18:00`
- Break rule: `10 minutes` after each `90-minute` focus block
- Default Ollama model: `qwen3:4b`

## Setup

```bash
python -m pip install -r requirements.txt
```

Optionally copy `.env.example` to `.env` and adjust values before running.

## Run

```bash
python -m uvicorn app.main:app --reload
```

In a second terminal for the dashboard:

```bash
cd frontend
npm install
npm run dev
```

Open:

- API root: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Frontend dashboard: `http://127.0.0.1:5173/`

Set `frontend/.env` from `frontend/.env.example` if your API is not running on `http://127.0.0.1:8000`.

## Demo Script

Start the backend first:

```bash
python -m uvicorn app.main:app --reload
```

Then run the scripted walkthrough from another terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo_focusflow.ps1
```

Optional:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo_focusflow.ps1 -DemoDate 2026-06-15
```

The script creates a demo goal, marks one linked task complete to show goal progress, adds mock calendar blocks, runs the full assistant workflow, and prints the resulting plan plus recent agent logs.

## Test

```bash
pytest
```

## Implemented Endpoints

- `GET /`
- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{id}`
- `PATCH /tasks/{id}`
- `DELETE /tasks/{id}`
- `POST /goals`
- `GET /goals`
- `GET /goals/progress`
- `GET /goals/{id}`
- `PATCH /goals/{id}`
- `DELETE /goals/{id}`
- `POST /calendar/events`
- `GET /calendar/events?date=YYYY-MM-DD`
- `GET /calendar/free-slots?date=YYYY-MM-DD`
- `POST /daily/plan`
- `POST /daily/checkin`
- `GET /daily/plan?date=YYYY-MM-DD`
- `GET /agent-logs?date=YYYY-MM-DD`
- `POST /assistant/daily-plan`
- `GET /notifications`
- `PATCH /notifications/{id}`
- `GET /dashboard/today`

## Notes

Goal progress uses a custom numeric value per task. If a completed task is edited, uncompleted, moved to a different goal, or deleted, the linked goal progress is adjusted automatically so totals stay consistent.

Daily plans now use deterministic scheduling rules: tasks are placed into workday free slots, split automatically when needed, and validated against overlaps, work hours, focus-block breaks, and priority ordering. If validation fails, the planner retries with a corrected ordering strategy and stores short human-readable agent logs.

Daily check-in now accepts natural-language input, uses Ollama for structured task extraction, persists those tasks into the database, and falls back to heuristic extraction if the local model is unavailable or returns unusable JSON.

The assistant workflow now uses LangGraph to orchestrate the `Daily`, `Calendar`, `Free-Time`, `Planning`, and `Validation` agents through one endpoint that turns a check-in message into a saved daily plan plus a workflow trace.

Iteration 7 adds a morning check-in reminder flow with idempotent daily notifications, a dashboard summary endpoint, and automatic clearing of the reminder once the user completes their check-in.

Iteration 8 adds a local React dashboard that connects to the FastAPI backend, runs the assistant workflow from a morning check-in, visualizes the day plan and goal progress, shows reminder state, and exposes quick-create controls for tasks and goals.
