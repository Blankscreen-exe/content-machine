"""Pieces: creation from an idea, stage changes, filters and due dates."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from cm import crud
from cm.models import Event, IdeaStatus, Piece


def test_make_a_piece_from_an_idea_and_promote_it(client: TestClient, session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="The cheapest technical decision")

    response = client.post(f"/ideas/{idea.id}/pieces",
                           data={"type": "carousel", "due_on": "2026-10-01"})
    assert response.status_code == 200

    piece = crud.list_pieces(session, idea_id=idea.id)[0]
    assert piece.title == idea.title
    assert piece.type.value == "carousel"
    assert piece.due_on == date(2026, 10, 1)
    assert piece.stage.value == "not started"

    session.refresh(idea)
    assert idea.status == IdeaStatus.promoted     # making a piece means the idea is in motion


def test_one_idea_can_produce_several_pieces(client: TestClient, session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Automation before AI")
    for piece_type in ("blog", "linkedin post", "x post"):
        client.post(f"/ideas/{idea.id}/pieces", data={"type": piece_type})

    assert {p.type.value for p in crud.list_pieces(session, idea_id=idea.id)} == {
        "blog", "linkedin post", "x post"
    }


def test_stage_change_is_recorded(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type="blog", title="Legacy systems")

    client.post(f"/pieces/{piece.id}/stage", data={"stage": "wip", "brand_id": brand.id})
    session.refresh(piece)
    assert piece.stage.value == "wip"

    events = session.exec(select(Event).where(Event.entity == "piece",
                                              Event.entity_id == piece.id)).all()
    assert [e.to_state for e in events] == ["not started", "wip"]


def test_filters_by_stage_and_type(client: TestClient, session: Session, brand):
    crud.create_piece(session, brand_id=brand.id, type="blog", title="A blog", stage="draft")
    crud.create_piece(session, brand_id=brand.id, type="carousel", title="A carousel", stage="ready")

    by_stage = client.get("/pieces/list", params={"stage": "ready"}).text
    assert "A carousel" in by_stage and "A blog" not in by_stage

    by_type = client.get("/pieces/list", params={"type": "blog"}).text
    assert "A blog" in by_type and "A carousel" not in by_type


def test_due_soonest_first_and_undated_last(session: Session, brand):
    later = crud.create_piece(session, brand_id=brand.id, type="blog", title="Later",
                              due_on=date.today() + timedelta(days=5))
    undated = crud.create_piece(session, brand_id=brand.id, type="blog", title="Undated")
    sooner = crud.create_piece(session, brand_id=brand.id, type="blog", title="Sooner",
                               due_on=date.today())

    assert [p.title for p in crud.list_pieces(session)] == ["Sooner", "Later", "Undated"]
    assert undated.due_on is None and later.due_on > sooner.due_on


def test_due_pieces_ignores_published_work(session: Session, brand):
    crud.create_piece(session, brand_id=brand.id, type="blog", title="Due today",
                      due_on=date.today())
    crud.create_piece(session, brand_id=brand.id, type="blog", title="Already out",
                      due_on=date.today(), stage="published")

    due = crud.due_pieces(session, on_or_before=date.today())
    assert [p.title for p in due] == ["Due today"]


def test_deleting_a_piece_leaves_the_idea(client: TestClient, session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Keep me")
    client.post(f"/ideas/{idea.id}/pieces", data={"type": "blog"})
    piece = crud.list_pieces(session, idea_id=idea.id)[0]

    client.post(f"/pieces/{piece.id}/delete")
    assert session.exec(select(Piece)).all() == []
    assert crud.get_idea(session, idea.id) is not None
