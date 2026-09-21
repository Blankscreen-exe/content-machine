"""The brand filter: a dropdown that decides what the lists show."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud
from helpers import type_id


def test_the_filter_is_a_labelled_dropdown_outside_the_header(client: TestClient, brand):
    """It changes what the list shows, so it has to read as a filter, not as part of the title."""
    for path in ("/", "/pieces"):
        page = client.get(path).text
        header = page[page.index('<header class="masthead">'):page.index("</header>")]
        assert "brand-scope" not in header, f"brand filter is back inside the header on {path}"
        assert '<select id="brand-scope" name="brand_id"' in page
        assert '<label class="scope-label" for="brand-scope">Showing</label>' in page


def test_the_current_brand_is_selected(client: TestClient, brand):
    page = client.get(f"/pieces?brand_id={brand.id}").text
    assert re.search(rf'<option value="{brand.id}"\s+selected', page)


def test_hidden_brands_are_not_offered(client: TestClient, session: Session, brand):
    crud.update_brand(session, brand, active=False)
    assert f'<option value="{brand.id}"' not in client.get("/ideas").text


def test_all_brands_sends_an_empty_value_and_that_is_accepted(client: TestClient, brand):
    """Browsers send `brand_id=` for "all brands"; that used to be a 422 on every list."""
    assert client.get("/ideas?brand_id=").status_code == 200
    assert client.get("/pieces?brand_id=").status_code == 200
    assert client.get("/ideas/list?brand_id=&q=anything").status_code == 200
    assert client.get("/pieces/list?brand_id=&stage=draft").status_code == 200


def test_a_single_piece_has_no_brand_filter(client: TestClient, session: Session, brand):
    """A piece belongs to one brand; a filter there would only navigate away."""
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A piece")
    assert "brand-scope" not in client.get(f"/pieces/{piece.id}").text


def test_new_piece_opens(client: TestClient, brand):
    """`/pieces/new` must not be swallowed by `/pieces/{piece_id}`."""
    assert client.get(f"/pieces/new?brand_id={brand.id}").status_code == 200
    assert client.get("/pieces/new?brand_id=").status_code == 200


def test_on_all_brands_a_new_idea_asks_which_brand(client: TestClient, brand):
    form = client.get("/ideas/new?brand_id=").text
    assert 'value="None"' not in form
    assert '<select name="brand_id" required' in form
    assert f'<option value="{brand.id}">{brand.slug}</option>' in form


def test_within_one_brand_a_new_idea_uses_it(client: TestClient, brand):
    form = client.get(f"/ideas/new?brand_id={brand.id}").text
    assert f'<input type="hidden" name="brand_id" value="{brand.id}">' in form
    assert '<select name="brand_id"' not in form


def test_on_all_brands_a_new_piece_asks_which_brand(client: TestClient, brand):
    form = client.get("/pieces/new?brand_id=").text
    assert 'value="None"' not in form
    assert '<select name="brand_id" required' in form
