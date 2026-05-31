import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel


TEST_DB_PATH = Path("tests/.test_focusflow.db")
os.environ["DATABASE_URL"] = "sqlite:///./tests/.test_focusflow.db"
os.environ["DEFAULT_USER_EMAIL"] = "test-user@focusflow.dev"
os.environ["ENABLE_REMINDER_SCHEDULER"] = "false"

from app.db import create_db_and_tables, engine, seed_default_user  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    SQLModel.metadata.drop_all(engine)
    create_db_and_tables()
    seed_default_user()

    with TestClient(app) as test_client:
        yield test_client

    SQLModel.metadata.drop_all(engine)
    engine.dispose()
