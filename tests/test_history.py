"""A piece's history: what its page says happened, who did it, and that it is only its own."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud
from cm.models import Actor
from helpers import type_id


def _rows(html: str) -> list[tuple[str, str]]:
    """(who, what) for each line of the history, as shown."""
    return re.findall(r"<td>(You|Claude)</td>\s*<td>(.*?)</td>", html)


def test_the_history_says_what_happened_and_who_did_it_newest_first(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Legacy systems")
    crud.update_piece(session, piece, title="Legacy systems age badly")
    crud.act_as(session, Actor.claude)
    crud.update_piece(session, piece, stage="draft")

    assert _rows(client.get(f"/pieces/{piece.id}/history").text) == [
        ("Claude", "not started → draft"),
        ("You", "edited: title"),
        ("You", "created (blog)"),
    ]


def test_a_new_piece_never_shows_a_deleted_ones_history(client: TestClient, session: Session, brand):
    blog = type_id(session, "blog")
    gone = crud.create_piece(session, brand_id=brand.id, type_id=blog, title="Old")
    gone_id = gone.id
    crud.delete_piece(session, gone)

    new = crud.create_piece(session, brand_id=brand.id, type_id=blog, title="New")

    assert new.id != gone_id
    assert _rows(client.get(f"/pieces/{new.id}/history").text) == [("You", "created (blog)")]


def test_the_piece_page_has_the_history_folded_away_until_opened(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Legacy systems")

    page = client.get(f"/pieces/{piece.id}").text

    assert f'hx-get="/pieces/{piece.id}/history"' in page
    assert "created (blog)" not in page        # fetched when opened, so it is never out of date


def test_no_history_for_a_piece_that_does_not_exist(client: TestClient):
    assert client.get("/pieces/999/history").status_code == 404
