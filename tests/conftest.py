"""Shared fixtures: an in-memory database and a client that is already authenticated."""
from __future__ import annotations

import os

# A fixed token for the whole run, so tests never create or read the real workspace's one.
# Set before the app is imported, because the token is looked up the first time it is used.
os.environ["CM_TOKEN"] = "test-token"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402
from sqlmodel.pool import StaticPool  # noqa: E402

from cm import choices, crud, terminals  # noqa: E402
from cm.app import create_app  # noqa: E402
from cm.database import enforce_foreign_keys, get_session  # noqa: E402
from cm.models import PieceType  # noqa: E402
from helpers import STANDARD_TYPES  # noqa: E402

TEST_TOKEN = os.environ["CM_TOKEN"]


@pytest.fixture(name="session")
def session_fixture():
    # the same foreign-key rules as the real database, or tests would pass on data it refuses
    engine = enforce_foreign_keys(create_engine("sqlite://", connect_args={"check_same_thread": False},
                                                poolclass=StaticPool))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for name, main_file, char_limit, video in STANDARD_TYPES:   # a real database gets these from migrations
            choices.create(session, PieceType, name, main_file=main_file, char_limit=char_limit,
                           video=video)
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app = create_app(run_migrations=False)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app, cookies={"cm_token": TEST_TOKEN}) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="brand")
def brand_fixture(session: Session):
    return crud.create_brand(session, "personal", "Example Person")


@pytest.fixture(name="local_client")
def local_client_fixture(session: Session):
    """A client that looks like it came from this machine."""
    app = create_app(run_migrations=False)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app, cookies={"cm_token": TEST_TOKEN}, client=("127.0.0.1", 45678)) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="launches")
def launches_fixture(monkeypatch):
    """Capture what would have been launched instead of opening a real terminal."""
    calls = []

    def fake_open(cwd, title, command, key=None):
        calls.append({"cwd": cwd, "title": title, "command": command, "key": key})
        return ["fake"]

    monkeypatch.setattr(terminals, "open_terminal", fake_open)
    monkeypatch.setattr(terminals, "claude_command", lambda prompt: ["claude", prompt])
    return calls
