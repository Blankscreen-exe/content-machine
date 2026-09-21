"""Checks on the rendered HTML that are easy to break by accident."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud


def test_first_render_has_no_duplicate_ids(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="Legacy systems age badly")
    page = client.get("/ideas").text
    assert page.count('id="count"') == 1
    assert page.count('id="editor"') == 1
    assert "hx-swap-oob" not in page          # nothing to swap on a full page load


def test_partial_carries_out_of_band_updates(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="Legacy systems age badly")
    partial = client.get("/ideas/list").text
    assert 'id="count"' in partial and "hx-swap-oob" in partial


def test_page_loads_local_assets_only(client: TestClient):
    page = client.get("/ideas").text
    assert "/static/vendor/htmx.min.js" in page
    assert "http://" not in page and "https://" not in page    # nothing fetched from the internet
