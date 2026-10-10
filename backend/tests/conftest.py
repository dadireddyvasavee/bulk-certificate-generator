# ruff: noqa: E402 -- Test environment must be configured before app imports.
import os
import tempfile
from pathlib import Path
import pytest

TEST_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(TEST_DIR.name) / "test.db")
os.environ["STORAGE_DIR"] = str(Path(TEST_DIR.name) / "storage")
os.environ["WORKER_MODE"] = "local"
from app.db import Base, engine
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def dispose_engine():
    # Release all pooled connections before the temporary database directory is
    # removed. Without this, Windows keeps the SQLite file open and the
    # TemporaryDirectory cleanup at interpreter exit raises PermissionError,
    # making the suite exit non-zero even when every test passes.
    yield
    engine.dispose()
    TEST_DIR.cleanup()


@pytest.fixture(autouse=True)
def clean():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def payload():
    return {
        "event": "Python Engineering",
        "organization": "Learning Lab",
        "title": "Certificate of Achievement",
        "statement": "For successfully completing the course",
        "signatory": "Course Director",
        "issue_date": "2026-10-09",
        "recipients": [
            {"name": "Alex Rivera", "email": "alex@example.com"},
            {"name": "Sam Taylor", "email": "sam@example.com"},
        ],
    }
