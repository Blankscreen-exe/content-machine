"""After a save or delete, the screen shows what it showed before, only updated.

Two ways this went wrong: saving on "all brands" narrowed the list to the item's brand
while the dropdown still said "all brands", and editing details on a piece's own page
aimed its result at a list that is not on that page.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud
from cm.settings import get_settings
from helpers import type_id


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture(name="other_brand")
def other_brand_fixture(session: Session):
    return crud.create_brand(session, "company", "Acme Co")


IDEA_FIELDS = {"title": "Renamed", "status": "pool", "priority": "2"}


def _piece_fields(session: Session) -> dict:
    return {"title": "Renamed", "type_id": type_id(session, "blog"), "stage": "draft",
            "due_on": "", "notes": ""}


# --- all brands stays all brands --------------------------------------------------------

def test_saving_an_idea_on_all_brands_keeps_every_brand_listed(client: TestClient, session: Session,
                                                                brand, other_brand):
    mine = crud.create_idea(session, brand_id=brand.id, title="Mine")
    crud.create_idea(session, brand_id=other_brand.id, title="Theirs")

    response = client.post(f"/ideas/{mine.id}", data=IDEA_FIELDS | {"view_brand_id": ""})

    assert "Renamed" in response.text and "Theirs" in response.text


def test_creating_an_idea_on_all_brands_keeps_every_brand_listed(client: TestClient, session: Session,
                                                                 brand, other_brand):
    crud.create_idea(session, brand_id=other_brand.id, title="Theirs")

    response = client.post("/ideas", data=IDEA_FIELDS | {"brand_id": brand.id, "view_brand_id": ""})

    assert "Renamed" in response.text and "Theirs" in response.text


def test_deleting_an_idea_on_all_brands_keeps_every_brand_listed(client: TestClient, session: Session,
                                                                 brand, other_brand):
    mine = crud.create_idea(session, brand_id=brand.id, title="Mine")
    crud.create_idea(session, brand_id=other_brand.id, title="Theirs")

    response = client.post(f"/ideas/{mine.id}/delete", data={"brand_id": ""})

    assert "Mine" not in response.text and "Theirs" in response.text


def test_saving_a_piece_on_all_brands_keeps_every_brand_listed(client: TestClient, session: Session,
                                                                brand, other_brand):
    mine = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")
    crud.create_piece(session, brand_id=other_brand.id, type_id=type_id(session, "blog"), title="Theirs")

    response = client.post(f"/pieces/{mine.id}", data=_piece_fields(session) | {"view_brand_id": ""})

    assert "Renamed" in response.text and "Theirs" in response.text


def test_deleting_a_piece_on_all_brands_keeps_every_brand_listed(client: TestClient, session: Session,
                                                                 brand, other_brand):
    mine = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")
    crud.create_piece(session, brand_id=other_brand.id, type_id=type_id(session, "blog"), title="Theirs")

    response = client.post(f"/pieces/{mine.id}/delete", data={"brand_id": ""})

    assert "Mine" not in response.text and "Theirs" in response.text


def test_changing_stage_on_all_brands_is_accepted(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")
    assert client.post(f"/pieces/{piece.id}/stage",
                       data={"stage": "draft", "brand_id": ""}).status_code == 200


def test_within_one_brand_saving_stays_within_it(client: TestClient, session: Session,
                                                 brand, other_brand):
    mine = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")
    crud.create_piece(session, brand_id=other_brand.id, type_id=type_id(session, "blog"), title="Theirs")

    response = client.post(f"/pieces/{mine.id}", data=_piece_fields(session) | {"view_brand_id": brand.id})

    assert "Renamed" in response.text and "Theirs" not in response.text


def test_edit_forms_carry_the_brand_being_viewed(client: TestClient, session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Mine")
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")
    hidden_empty = '<input type="hidden" name="view_brand_id" value="">'

    assert hidden_empty in client.get(f"/ideas/{idea.id}?brand_id=").text
    assert hidden_empty in client.get(f"/pieces/{piece.id}/form?brand_id=").text


# --- the piece's own page ---------------------------------------------------------------

def test_edit_details_on_the_piece_page_redraws_its_heading(client: TestClient, session: Session,
                                                            brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Before")

    form = client.get(f"/pieces/{piece.id}/form?origin=page").text
    assert 'hx-target="#piece-head"' in form

    response = client.post(f"/pieces/{piece.id}", data=_piece_fields(session) | {"origin": "page"})

    assert 'id="piece-head"' in response.text and "Renamed" in response.text
    assert 'id="pieces"' not in response.text            # there is no list on that page
    assert '<div id="piece-editor" hx-swap-oob="true"></div>' in response.text


def test_deleting_from_the_piece_page_goes_back_to_the_list(client: TestClient, session: Session,
                                                            brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")

    response = client.post(f"/pieces/{piece.id}/delete", data={"origin": "page"})

    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == f"/pieces?brand_id={brand.id}"
    assert crud.get_piece(session, piece.id) is None
