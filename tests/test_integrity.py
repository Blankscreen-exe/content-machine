"""Links between tables are enforced, and deletes say what happens to what depends on them."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from cm import crud
from cm.models import Idea, Piece, Publication
from helpers import platform_id, type_id


def test_foreign_keys_are_enforced(session: Session):
    assert session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_a_piece_cannot_point_at_a_brand_that_does_not_exist(session: Session):
    session.add(Piece(brand_id=999, type_id=type_id(session, "blog"), title="Orphan",
                      slug="orphan-blog"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_deleting_an_idea_keeps_its_pieces_as_standalone(session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Cheap decisions compound")
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title=idea.title,
                              idea_id=idea.id)

    crud.delete_idea(session, idea)

    session.refresh(piece)
    assert piece.idea_id is None
    assert session.exec(select(Idea)).all() == []


def test_deleting_a_piece_removes_its_publication_records(session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Out in the world")
    crud.record_publication(session, piece, platform_id=platform_id(session, "blog"),
                            url="https://example.com/post")

    crud.delete_piece(session, piece)

    assert session.exec(select(Piece)).all() == []
    assert session.exec(select(Publication)).all() == []
