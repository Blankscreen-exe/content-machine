"""The Settings tab: appearance, terminal and brands."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud


def test_settings_page_shows_the_workspace_and_brands(client: TestClient, session: Session, brand):
    page = client.get("/settings").text

    assert "Appearance" in page and "Terminal" in page and "Brands" in page
    assert brand.slug in page
    assert "content.db" in page                    # where the data actually lives


def test_every_page_offers_the_same_three_tabs(client: TestClient, brand):
    for path in ("/", "/pieces", "/settings"):
        page = client.get(path).text
        assert page.count('class="tabs"') == 1
        for label in (">Ideas<", ">Pieces<", ">Settings<"):
            assert label in page, f"{label} missing from {path}"


def test_settings_page_has_no_brand_filter(client: TestClient, brand):
    """The brand filter applies to ideas and pieces, not to settings."""
    assert 'class="brands"' not in client.get("/settings").text
    assert 'class="brands"' in client.get("/").text


def test_adding_a_brand_returns_the_updated_list(client: TestClient, session: Session):
    response = client.post("/brands", data={"slug": "acme", "name": "Acme Co"})

    assert response.status_code == 200
    assert "Acme Co" in response.text
    assert crud.get_brand_by_slug(session, "acme") is not None


def test_renaming_a_brand(client: TestClient, session: Session, brand):
    client.post(f"/brands/{brand.id}", data={"name": "A New Name"})
    session.refresh(brand)
    assert brand.name == "A New Name"


def test_hiding_a_brand_keeps_its_work(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="Still here")

    client.post(f"/brands/{brand.id}/active", data={"active": "false"})

    session.refresh(brand)
    assert brand.active is False
    assert len(crud.list_ideas(session, brand_id=brand.id)) == 1
    assert brand.slug not in client.get("/").text      # hidden from the filter only


def test_rows_have_edit_and_delete_buttons(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="An idea")
    crud.create_piece(session, brand_id=brand.id, type="blog", title="A piece")

    ideas_page = client.get("/").text
    assert ">Edit<" in ideas_page and ">Delete<" in ideas_page

    pieces_page = client.get("/pieces").text
    assert ">Edit<" in pieces_page and ">Delete<" in pieces_page
