"""Ideas CRUD through the HTTP layer, against a temporary database."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from cm import crud
from cm.app import create_app
from cm.models import Event


def test_token_is_required():
    with TestClient(create_app(run_migrations=False)) as anonymous:
        assert anonymous.get("/").status_code == 403


def test_create_edit_and_delete_an_idea(client: TestClient, session: Session, brand):
    created = client.post("/ideas", data={
        "brand_id": brand.id, "title": "The cheapest technical decision",
        "angle": "cheap now, expensive later", "status": "pool", "priority": 1,
    })
    assert created.status_code == 200
    assert "The cheapest technical decision" in created.text

    idea = crud.list_ideas(session)[0]
    updated = client.post(f"/ideas/{idea.id}", data={
        "title": idea.title, "status": "promoted", "priority": 2,
    })
    assert updated.status_code == 200
    session.refresh(idea)
    assert idea.status.value == "promoted"

    deleted = client.post(f"/ideas/{idea.id}/delete")
    assert deleted.status_code == 200
    assert crud.list_ideas(session) == []


def test_status_change_is_recorded(client: TestClient, session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Automation before AI")
    client.post(f"/ideas/{idea.id}", data={"title": idea.title, "status": "parked", "priority": 2})

    events = session.exec(select(Event).where(Event.entity_id == idea.id)).all()
    assert [e.to_state for e in events] == ["pool", "parked"]


def test_search_and_status_filters(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="Legacy systems age badly")
    crud.create_idea(session, brand_id=brand.id, title="Automation before AI", status="parked")

    assert "Legacy" in client.get("/ideas", params={"q": "legacy"}).text
    assert "Automation" not in client.get("/ideas", params={"q": "legacy"}).text
    assert "Automation" in client.get("/ideas", params={"status": "parked"}).text
    assert "Legacy" not in client.get("/ideas", params={"status": "parked"}).text


def test_missing_idea_returns_404(client: TestClient):
    assert client.get("/ideas/999").status_code == 404


def test_theme_setting_persists(client: TestClient, session: Session):
    response = client.post("/settings", data={"key": "theme", "value": "scholar"})
    assert response.status_code == 204
    assert response.headers["HX-Refresh"] == "true"      # the stylesheet has to be reloaded
    assert crud.get_settings_map(session)["theme"] == "scholar"


def test_terminal_setting_persists_without_reloading(client: TestClient, session: Session):
    response = client.post("/settings", data={"key": "terminal", "value": "kitty"})
    assert response.status_code == 204
    assert "HX-Refresh" not in response.headers
    assert crud.get_settings_map(session)["terminal"] == "kitty"


def test_unknown_settings_are_rejected(client: TestClient):
    assert client.post("/settings", data={"key": "shell", "value": "rm -rf"}).status_code == 400

