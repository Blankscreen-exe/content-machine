"""After a save or delete, the screen shows what it showed before, only updated.

Two ways this went wrong: saving on "all brands" narrowed the list to the item's brand
while the dropdown still said "all brands", and editing details on a piece's own page
aimed its result at a list that is not on that page. A piece's details are now edited on a
page of their own, which goes back to the page it was opened from; these check that it
does, exactly, and that it can only ever go back to a page of this app.
"""
from __future__ import annotations

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud
from cm.routes.params import back_to
from cm.settings import get_settings
from helpers import type_id


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture(name="other_brand")
def other_brand_fixture(session: Session):
    return crud.create_brand(session, "company", "Acme Co")


def _piece_fields(session: Session) -> dict:
    return {"title": "Renamed", "type_id": type_id(session, "blog"), "stage": "draft",
            "due_on": "", "notes": ""}


# --- all brands stays all brands --------------------------------------------------------

def test_deleting_an_idea_on_all_brands_keeps_every_brand_listed(client: TestClient, session: Session,
                                                                 brand, other_brand):
    mine = crud.create_idea(session, brand_id=brand.id, title="Mine")
    crud.create_idea(session, brand_id=other_brand.id, title="Theirs")

    response = client.post(f"/ideas/{mine.id}/delete", data={"brand_id": ""})

    assert "Mine" not in response.text and "Theirs" in response.text


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


# --- the edit page goes back to where it was opened -------------------------------------

def test_the_list_sends_its_own_address_to_the_edit_page(client: TestClient, session: Session,
                                                        brand, other_brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")

    one_brand = client.get(f"/pieces?brand_id={brand.id}").text
    all_brands = client.get("/pieces").text

    assert f'/pieces/{piece.id}/edit?next={quote(f"/pieces?brand_id={brand.id}", safe="/")}' in one_brand
    assert f'/pieces/{piece.id}/edit?next=/pieces"' in all_brands


def test_saving_goes_back_to_the_list_it_came_from(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")
    back = f"/pieces?brand_id={brand.id}&stage=draft"

    page = client.get(f"/pieces/{piece.id}/edit", params={"next": back}).text
    response = client.post(f"/pieces/{piece.id}", data=_piece_fields(session) | {"next": back})

    assert f'name="next" value="{back.replace("&", "&amp;")}"' in page
    assert response.status_code == 204 and response.headers["HX-Redirect"] == back
    assert crud.get_piece(session, piece.id).title == "Renamed"


def test_edit_details_on_the_piece_page_goes_back_to_the_piece(client: TestClient, session: Session,
                                                              brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Before")
    own_page = f"/pieces/{piece.id}"

    assert f'href="{own_page}/edit?next={own_page}"' in client.get(own_page).text
    edit_page = client.get(f"{own_page}/edit", params={"next": own_page}).text
    response = client.post(own_page, data=_piece_fields(session) | {"next": own_page})

    assert "&larr; Before" in edit_page                   # the way back names where it goes
    assert response.headers["HX-Redirect"] == own_page


def test_a_new_piece_opens_on_its_own_page(client: TestClient, session: Session, brand):
    response = client.post("/pieces", data=_piece_fields(session) | {"brand_id": brand.id})

    made = crud.list_pieces(session)[0]
    assert response.status_code == 204 and response.headers["HX-Redirect"] == f"/pieces/{made.id}"


def test_deleting_from_the_piece_page_goes_back_to_the_list(client: TestClient, session: Session,
                                                            brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")

    response = client.post(f"/pieces/{piece.id}/delete", data={"origin": "page"})

    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == f"/pieces?brand_id={brand.id}"
    assert crud.get_piece(session, piece.id) is None


# --- and only ever to a page of this app -----------------------------------------------

@pytest.mark.parametrize("wanted", ["/pieces", "/pieces?brand_id=2&stage=draft", "/pieces/7"])
def test_a_page_of_this_app_is_gone_back_to(wanted):
    assert back_to(wanted, "/fallback") == wanted


@pytest.mark.parametrize("wanted", [
    None, "", "https://example.com/", "//example.com/", "/\\example.com/",
    "/\t/example.com/", "/\n/example.com", "pieces", "javascript:alert(1)",
])
def test_anywhere_else_falls_back(wanted):
    """A crafted link must not send someone to another site once they save."""
    assert back_to(wanted, "/fallback") == "/fallback"


def test_saving_with_a_foreign_address_stays_in_the_app(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Mine")

    response = client.post(f"/pieces/{piece.id}", data=_piece_fields(session) | {"next": "//example.com"})

    assert response.headers["HX-Redirect"] == f"/pieces/{piece.id}"
