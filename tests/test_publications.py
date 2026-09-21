"""Recording where a piece was published, from its page."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import choices, crud
from cm.models import Platform, Stage
from cm.settings import get_settings
from helpers import platform_id, type_id


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture(name="piece")
def piece_fixture(session: Session, brand):
    return crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Legacy systems",
                             stage=Stage.ready)


def test_the_piece_page_offers_to_record_a_publish(client: TestClient, session: Session, piece):
    platform_id(session, "blog")
    page = client.get(f"/pieces/{piece.id}").text
    assert f'hx-post="/pieces/{piece.id}/publications"' in page
    assert "Not published anywhere yet." in page


def test_recording_a_publish_lists_it_and_marks_the_piece_published(client: TestClient,
                                                                    session: Session, piece):
    response = client.post(f"/pieces/{piece.id}/publications",
                           data={"platform_id": platform_id(session, "blog"),
                                 "url": "https://example.com/post", "posted_on": "2026-09-01"})

    assert response.status_code == 200
    assert ">2026-09-01<" in response.text and "https://example.com/post" in response.text
    session.refresh(piece)
    assert piece.stage == Stage.published
    # the heading shows the stage, so it is redrawn alongside the panel
    assert 'id="piece-head" hx-swap-oob="true"' in response.text
    assert crud.list_publications(session, piece.id)[0].platform.name == "blog"


def test_the_form_offers_the_active_platforms(client: TestClient, session: Session, piece):
    newsletter = platform_id(session, "newsletter")
    choices.create(session, Platform, "old forum", active=False)

    page = client.get(f"/pieces/{piece.id}").text

    assert f'<option value="{newsletter}">newsletter</option>' in page
    assert "old forum" not in page


def test_with_no_platforms_the_page_says_where_to_add_one(client: TestClient, piece):
    page = client.get(f"/pieces/{piece.id}").text
    assert 'name="platform_id"' not in page
    assert "add a platform under" in page


def test_removing_a_record_keeps_the_stage(client: TestClient, session: Session, piece):
    publication = crud.record_publication(session, piece, platform_id=platform_id(session, "blog"))

    response = client.post(f"/pieces/{piece.id}/publications/{publication.id}/delete")

    assert response.status_code == 200
    assert crud.list_publications(session, piece.id) == []
    session.refresh(piece)
    assert piece.stage == Stage.published


def test_a_record_can_only_be_removed_through_its_own_piece(client: TestClient, session: Session,
                                                            brand, piece):
    other = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Other")
    publication = crud.record_publication(session, other, platform_id=platform_id(session, "blog"))

    response = client.post(f"/pieces/{piece.id}/publications/{publication.id}/delete")

    assert response.status_code == 404
    assert len(crud.list_publications(session, other.id)) == 1


def test_a_date_is_required(client: TestClient, session: Session, piece):
    response = client.post(f"/pieces/{piece.id}/publications",
                           data={"platform_id": platform_id(session, "blog")})
    assert response.status_code == 422
    assert crud.list_publications(session, piece.id) == []
