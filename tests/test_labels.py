"""What people see for statuses and priorities, versus what is stored."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud
from cm.models import PRIORITIES
from cm.templating import status_class


def test_status_class_names_are_css_safe():
    assert status_class("not started") == "status-not-started"
    assert status_class("wip") == "status-wip"


def test_the_ideas_list_shows_priority_names(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="Urgent one", priority=1)
    crud.create_idea(session, brand_id=brand.id, title="Someday one", priority=3)

    page = client.get("/").text
    assert ">high<" in page and ">low<" in page
    assert page.index("Urgent one") < page.index("Someday one")     # still sorted by the number


def test_the_editor_offers_names_but_submits_numbers(client: TestClient, session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="An idea", priority=2)
    form = client.get(f"/ideas/{idea.id}").text
    for number, name in PRIORITIES.items():
        assert f'<option value="{number}"' in form and f">{name}</option>" in form

    client.post(f"/ideas/{idea.id}", data={"title": idea.title, "status": "pool", "priority": 1})
    session.refresh(idea)
    assert idea.priority == 1


def test_statuses_and_stages_carry_their_colour_class(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="Parked one", status="parked")
    piece = crud.create_piece(session, brand_id=brand.id, type="blog", title="A piece", stage="wip")

    assert 'class="status status-parked"' in client.get("/").text
    assert 'class="status status-wip"' in client.get("/pieces").text           # the inline picker
    assert 'class="status status-wip"' in client.get(f"/pieces/{piece.id}").text  # the piece heading
