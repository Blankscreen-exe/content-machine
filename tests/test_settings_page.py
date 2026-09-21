"""The Settings tab: preferences and where the workspace is; and the tabs every page shares."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud
from helpers import type_id

TABS = (">Ideas", ">Pieces", ">Calendar", ">Manage", ">Settings")   # Calendar may carry a count


def test_settings_page_shows_preferences_and_the_workspace(client: TestClient, brand):
    page = client.get("/settings").text

    assert "Appearance" in page and "Terminal" in page and "Reminders" in page
    assert "content.db" in page                    # where the data actually lives
    assert "Add brand" not in page                 # brands are managed under Manage


def test_every_page_offers_the_same_tabs(client: TestClient, brand):
    for path in ("/", "/pieces", "/calendar", "/manage/brands", "/settings"):
        page = client.get(path).text
        assert page.count('class="tabs"') == 1
        for label in TABS:
            assert label in page, f"{label} missing from {path}"


def test_settings_page_has_no_brand_filter(client: TestClient, brand):
    """The brand filter applies to ideas and pieces, not to settings."""
    assert 'class="scope"' not in client.get("/settings").text
    assert 'class="scope"' in client.get("/").text


def test_rows_have_edit_and_delete_buttons(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="An idea")
    crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A piece")

    ideas_page = client.get("/").text
    assert ">Edit<" in ideas_page and ">Delete<" in ideas_page

    pieces_page = client.get("/pieces").text
    assert ">Edit<" in pieces_page and ">Delete<" in pieces_page
