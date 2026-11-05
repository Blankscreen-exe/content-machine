"""Ideas CRUD through the HTTP layer, against a temporary database."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from cm import crud
from cm.app import create_app
from cm.models import Event
from helpers import type_id


def test_token_is_required():
    with TestClient(create_app(run_migrations=False)) as anonymous:
        assert anonymous.get("/").status_code == 403


def test_create_edit_and_delete_an_idea(client: TestClient, session: Session, brand):
    created = client.post("/ideas", data={
        "brand_id": brand.id, "title": "The cheapest technical decision",
        "angle": "cheap now, expensive later", "status": "pool", "priority": 1,
    })
    idea = crud.list_ideas(session)[0]
    # a new idea opens on its own page, where pieces can be made from it
    assert created.status_code == 204 and created.headers["HX-Redirect"] == f"/ideas/{idea.id}"
    assert "The cheapest technical decision" in client.get(f"/ideas/{idea.id}").text

    updated = client.post(f"/ideas/{idea.id}", data={
        "title": idea.title, "status": "promoted", "priority": 2,
    })
    assert updated.status_code == 200 and "Saved" in updated.text
    assert 'id="idea-head" hx-swap-oob="true"' in updated.text     # the heading shows the status
    session.refresh(idea)
    assert idea.status.value == "promoted"

    deleted = client.post(f"/ideas/{idea.id}/delete")
    assert deleted.status_code == 200
    assert crud.list_ideas(session) == []


def test_deleting_from_the_ideas_page_goes_back_to_the_list(client: TestClient, session: Session,
                                                            brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Gone soon")

    response = client.post(f"/ideas/{idea.id}/delete", data={"origin": "page"})

    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == f"/ideas?brand_id={brand.id}"


def test_an_ideas_page_links_the_pieces_made_from_it(client: TestClient, session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Automation before AI")
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"),
                              title=idea.title, idea_id=idea.id)

    page = client.get(f"/ideas/{idea.id}").text

    assert f'href="/pieces/{piece.id}"' in page[page.index('id="idea-pieces"'):]
    assert f'href="/ideas/{idea.id}"' in client.get("/ideas").text        # the list opens the page


def test_making_a_piece_on_the_ideas_page_redraws_its_list_and_heading(client: TestClient,
                                                                       session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Automation before AI")

    response = client.post(f"/ideas/{idea.id}/pieces", data={"type_id": type_id(session, "blog")})

    assert 'id="idea-pieces"' in response.text and "Automation before AI" in response.text
    # making a piece promotes an idea still in the pool, which the heading shows
    assert 'id="idea-head" hx-swap-oob="true"' in response.text and "promoted" in response.text


def test_status_change_is_recorded(client: TestClient, session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Automation before AI")
    client.post(f"/ideas/{idea.id}", data={"title": idea.title, "status": "parked", "priority": 2})

    events = session.exec(select(Event).where(Event.entity_id == idea.id)).all()
    assert [e.to_state for e in events] == ["pool", "parked"]


def test_search_and_status_filters(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="Legacy systems age badly")
    crud.create_idea(session, brand_id=brand.id, title="Automation before AI", status="parked")

    assert "Legacy" in client.get("/ideas/list", params={"q": "legacy"}).text
    assert "Automation" not in client.get("/ideas/list", params={"q": "legacy"}).text
    assert "Automation" in client.get("/ideas/list", params={"status": "parked"}).text
    assert "Legacy" not in client.get("/ideas/list", params={"status": "parked"}).text


def test_missing_idea_returns_404(client: TestClient):
    assert client.get("/ideas/999").status_code == 404


def test_theme_setting_persists(client: TestClient, session: Session):
    response = client.post("/settings", data={"key": "theme", "value": "cyberdeck"})
    assert response.status_code == 204
    assert response.headers["HX-Refresh"] == "true"      # the stylesheet has to be reloaded
    assert crud.get_settings_map(session)["theme"] == "cyberdeck"


def test_only_a_theme_that_exists_can_be_chosen(client: TestClient, session: Session):
    response = client.post("/settings", data={"key": "theme", "value": "../../secrets"})
    assert response.status_code == 400 and "cm/static/themes/" in response.json()["detail"]
    assert crud.get_settings_map(session)["theme"] == crud.DEFAULT_SETTINGS["theme"]


def test_a_theme_removed_after_it_was_chosen_falls_back_to_the_default(client: TestClient,
                                                                       session: Session):
    """A page linking a stylesheet that is not there would arrive unstyled."""
    crud.set_setting(session, "theme", "a-theme-since-deleted")
    page = client.get("/").text
    assert f'/static/themes/{crud.DEFAULT_SETTINGS["theme"]}.css' in page
    assert "a-theme-since-deleted" not in page


def test_terminal_setting_persists_without_reloading(client: TestClient, session: Session):
    response = client.post("/settings", data={"key": "terminal", "value": "kitty"})
    assert response.status_code == 204
    assert "HX-Refresh" not in response.headers
    assert crud.get_settings_map(session)["terminal"] == "kitty"


def test_unknown_settings_are_rejected(client: TestClient):
    assert client.post("/settings", data={"key": "shell", "value": "rm -rf"}).status_code == 400

