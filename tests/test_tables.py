"""The lists are paged and sortable by DataTables, loaded from this app, never the internet."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import choices, crud
from cm.models import Platform
from cm.paths import STATIC_DIR
from helpers import type_id

# (page, the table's id) for every list that is paged
LISTS = [
    ("/", "ideas-table"),
    ("/pieces", "pieces-table"),
    ("/manage/brands", "brands-table"),
    ("/manage/types", "types-table"),
    ("/manage/platforms", "platforms-table"),
]


@pytest.fixture(autouse=True)
def rows(session: Session, brand):
    """One row in each list, so each one renders its table rather than its empty message."""
    crud.create_idea(session, brand_id=brand.id, title="An idea")
    crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A piece")
    choices.create(session, Platform, "newsletter")


@pytest.mark.parametrize("path, table_id", LISTS)
def test_every_list_opts_in_to_paging(client: TestClient, path, table_id):
    page = client.get(path).text
    assert f'id="{table_id}" data-table' in page
    assert re.search(r'<th class="actions-head no-sort">', page), "buttons are not a sortable column"


def test_the_paging_library_is_served_from_the_app(client: TestClient):
    page = client.get("/pieces").text
    for path in ("/static/vendor/datatables.min.js", "/static/vendor/datatables.min.css",
                 "/static/tables.js"):
        assert path in page
        assert client.get(path).status_code == 200
    assert (STATIC_DIR / "vendor" / "datatables.min.js").read_text(encoding="utf-8").startswith(
        "/*! DataTables 3.")


def test_cells_that_hold_controls_sort_by_their_value(client: TestClient, session: Session, brand):
    page = client.get("/pieces").text
    assert 'data-label="Stage" data-order="0"' in page          # "not started" is the first stage
    assert 'data-order="9999-12-31"' in page                     # undated work sorts last
