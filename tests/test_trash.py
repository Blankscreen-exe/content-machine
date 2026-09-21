"""Deleting a piece moves its folder to the trash: deleting the entry never deletes the work."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, workspace
from cm.settings import get_settings


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


def _piece_with_a_draft(session: Session, brand, title="Legacy systems"):
    piece = crud.create_piece(session, brand_id=brand.id, type="blog", title=title)
    folder = workspace.ensure_folder(session, piece)
    (folder / "blog.md").write_text("words worth keeping", encoding="utf-8")
    return piece, folder


def test_the_folder_goes_to_the_trash_with_its_files(session: Session, brand):
    piece, folder = _piece_with_a_draft(session, brand)

    trashed = workspace.delete_piece(session, piece)

    assert not folder.exists()
    assert trashed == get_settings().trash_dir / brand.slug / folder.name
    assert (trashed / "blog.md").read_text(encoding="utf-8") == "words worth keeping"
    assert crud.get_piece(session, piece.id) is None


def test_a_piece_without_a_folder_is_simply_deleted(session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type="blog", title="Never opened")
    assert workspace.delete_piece(session, piece) is None
    assert crud.get_piece(session, piece.id) is None


def test_a_name_already_in_the_trash_is_not_overwritten(session: Session, brand):
    piece, folder = _piece_with_a_draft(session, brand)
    earlier = get_settings().trash_dir / brand.slug / folder.name
    earlier.mkdir(parents=True)
    (earlier / "blog.md").write_text("an earlier piece", encoding="utf-8")

    trashed = workspace.delete_piece(session, piece)

    assert trashed.name == f"{folder.name}-2"
    assert (earlier / "blog.md").read_text(encoding="utf-8") == "an earlier piece"


def test_a_folder_that_cannot_move_stops_the_delete(client: TestClient, session: Session, brand,
                                                    monkeypatch):
    """On Windows a terminal open in the folder blocks the move; the entry must survive that."""
    piece, folder = _piece_with_a_draft(session, brand)

    def locked(self, target):
        raise PermissionError(13, "The folder is in use")

    monkeypatch.setattr(type(folder), "rename", locked)
    response = client.post(f"/pieces/{piece.id}/delete", data={"brand_id": ""})

    assert response.status_code == 409
    assert "could not be moved to the trash" in response.json()["detail"]
    assert crud.get_piece(session, piece.id) is not None
    assert (folder / "blog.md").exists()


def test_a_failed_delete_puts_the_folder_back(session: Session, brand, monkeypatch):
    piece, folder = _piece_with_a_draft(session, brand)

    def refuse(*args, **kwargs):
        raise RuntimeError("database said no")

    monkeypatch.setattr(crud, "delete_piece", refuse)
    with pytest.raises(RuntimeError):
        workspace.delete_piece(session, piece)

    assert (folder / "blog.md").read_text(encoding="utf-8") == "words worth keeping"
