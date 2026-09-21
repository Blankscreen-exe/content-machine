"""Opening a terminal session for a piece."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, terminals
from cm.app import create_app
from cm.database import get_session
from cm.settings import get_settings
from helpers import type_id

TEST_TOKEN = os.environ["CM_TOKEN"]      # set by conftest before anything is imported


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


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


def test_remote_callers_are_refused(client: TestClient, session: Session, brand, launches):
    """The app can be served on the LAN; only this machine may start processes on it."""
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Legacy systems")

    response = client.post(f"/pieces/{piece.id}/session")     # default client host: "testclient"

    assert response.status_code == 200
    assert "only be started on the machine running the app" in response.text
    assert launches == []


def test_local_call_writes_the_brief_and_opens_a_terminal(local_client: TestClient,
                                                          session: Session, brand, launches):
    idea = crud.create_idea(session, brand_id=brand.id, title="Cheap decisions compound",
                            angle="cheap now, expensive later")
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "carousel"),
                              title="Cheap decisions compound", idea_id=idea.id)

    response = local_client.post(f"/pieces/{piece.id}/session")
    assert response.status_code == 200

    assert len(launches) == 1
    launch = launches[0]
    assert (launch["cwd"] / "brief.md").exists()
    assert "cheap now, expensive later" in (launch["cwd"] / "brief.md").read_text(encoding="utf-8")
    assert piece.title in launch["title"]
    assert launch["command"][0] == "claude"


def test_chosen_terminal_is_passed_through(local_client: TestClient, session: Session,
                                           brand, launches):
    crud.set_setting(session, "terminal", "kitty")
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A piece")

    local_client.post(f"/pieces/{piece.id}/session")
    assert launches[0]["key"] == "kitty"


def test_a_missing_terminal_is_reported_not_swallowed(local_client: TestClient, session: Session,
                                                      brand, monkeypatch):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A piece")

    def boom(*args, **kwargs):
        raise terminals.TerminalError("No supported terminal found.")

    monkeypatch.setattr(terminals, "claude_command", lambda prompt: ["claude", prompt])
    monkeypatch.setattr(terminals, "open_terminal", boom)

    response = local_client.post(f"/pieces/{piece.id}/session")
    assert "No supported terminal found." in response.text
