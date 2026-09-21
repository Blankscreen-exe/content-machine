"""Searching inside drafts: found by their words, kept in step with the files on disk."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, search, workspace
from cm.settings import get_settings
from helpers import type_id


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


def _draft(session: Session, brand, title: str, text: str, name: str = "blog.md"):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title=title)
    folder = workspace.ensure_folder(session, piece)
    (folder / name).write_text(text, encoding="utf-8")
    return piece, folder / name


def _titles(hits):
    return [hit.piece.title for hit in hits]


def test_a_word_in_a_draft_finds_its_piece(session: Session, brand):
    _draft(session, brand, "Queues", "Why queues beat cron for background work.")
    _draft(session, brand, "Caching", "Five caching mistakes.")

    assert _titles(search.search(session, "cron")) == ["Queues"]


def test_every_word_has_to_be_there(session: Session, brand):
    _draft(session, brand, "Queues", "Why queues beat cron.")
    assert search.search(session, "queues caching") == []


def test_word_forms_and_unfinished_words_match(session: Session, brand):
    _draft(session, brand, "Queues", "Why queues beat cron for background work.")
    assert _titles(search.search(session, "queue")) == ["Queues"]          # stemmed
    assert _titles(search.search(session, "backgr")) == ["Queues"]         # still typing


def test_the_match_is_marked_and_the_rest_escaped(session: Session, brand):
    _draft(session, brand, "Markup", "Never paste <script>alert(1)</script> near the cron job.")

    snippet = search.search(session, "cron")[0].snippet

    assert "<mark>cron</mark>" in snippet
    assert "<script>" not in snippet and "&lt;script&gt;" in snippet


def test_anything_typed_is_safe_to_search_for(session: Session, brand):
    _draft(session, brand, "Queues", "Why queues beat cron.")
    for typed in ('"', "AND OR NOT", "cron*)", "NEAR(", "^:", "   "):
        search.search(session, typed)                     # no FTS5 syntax error escapes


def test_an_edit_made_outside_the_app_is_found(session: Session, brand):
    """Terminal sessions write drafts directly; the next search has to see it."""
    _, path = _draft(session, brand, "Queues", "Why queues beat cron.")
    assert search.search(session, "kafka") == []

    path.write_text("Why queues beat cron, and when kafka is too much.", encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))   # a later save

    assert _titles(search.search(session, "kafka")) == ["Queues"]


def test_a_deleted_draft_stops_being_found(session: Session, brand):
    _, path = _draft(session, brand, "Queues", "Why queues beat cron.")
    assert search.search(session, "cron")

    path.unlink()
    assert search.search(session, "cron") == []


def test_the_generated_brief_is_not_searched(session: Session, brand):
    piece, _ = _draft(session, brand, "Queues", "Why queues beat cron.")
    workspace.write_brief(session, piece)                 # contains "cm stage", "Voice"...
    assert search.search(session, "generated") == []


def test_results_stay_within_the_brand_being_viewed(session: Session, brand):
    other = crud.create_brand(session, "acme", "Acme Co")
    _draft(session, brand, "Mine", "cron everywhere")
    _draft(session, other, "Theirs", "cron everywhere")

    assert _titles(search.search(session, "cron", brand_id=other.id)) == ["Theirs"]
    assert sorted(_titles(search.search(session, "cron"))) == ["Mine", "Theirs"]


def test_the_index_is_a_cache_in_the_workspace(session: Session, brand, workspace_dir):
    _draft(session, brand, "Queues", "Why queues beat cron.")
    search.search(session, "cron")
    index = workspace_dir / ".cm" / "search.db"
    assert index.exists()

    index.unlink()                                        # deleting it loses nothing
    assert _titles(search.search(session, "cron")) == ["Queues"]


def test_the_pieces_page_searches_and_links_to_the_file_found(client: TestClient,
                                                             session: Session, brand):
    piece, _ = _draft(session, brand, "Queues", "Why queues beat cron.", name="notes.md")
    assert 'placeholder="search drafts..."' in client.get("/pieces").text

    results = client.get("/pieces/search", params={"q": "cron", "brand_id": ""}).text

    assert f'href="/pieces/{piece.id}?file=notes.md"' in results
    page = client.get(f"/pieces/{piece.id}?file=notes.md").text
    assert "Why queues beat cron." in page                # opened on the file that matched


def test_an_unknown_file_opens_the_main_draft(client: TestClient, session: Session, brand):
    piece, _ = _draft(session, brand, "Queues", "Main text.")
    page = client.get(f"/pieces/{piece.id}?file=../../content.db").text
    assert "Main text." in page


def test_nothing_typed_shows_nothing(client: TestClient):
    assert "Found in drafts" not in client.get("/pieces/search", params={"q": " "}).text
