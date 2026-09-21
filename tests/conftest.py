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

from cm import crud  # noqa: E402
from cm.app import create_app  # noqa: E402
from cm.database import enforce_foreign_keys, get_session  # noqa: E402

TEST_TOKEN = os.environ["CM_TOKEN"]


@pytest.fixture(name="session")
def session_fixture():
    # the same foreign-key rules as the real database, or tests would pass on data it refuses
    engine = enforce_foreign_keys(create_engine("sqlite://", connect_args={"check_same_thread": False},
                                                poolclass=StaticPool))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
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
