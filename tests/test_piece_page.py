"""The piece page and its editor, over HTTP."""
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


@pytest.fixture(name="piece")
def piece_fixture(session: Session, brand):
    return crud.create_piece(session, brand_id=brand.id, type="blog",
                             title="The cheapest technical decision")


def test_page_opens_the_main_draft_for_the_type(client: TestClient, piece):
    page = client.get(f"/pieces/{piece.id}").text

    assert piece.title in page
    assert "blog.md" in page
    assert 'id="draft-text"' in page
    assert "Copy as markdown" in page and "Copy as plain text" in page


def test_saving_creates_the_file(client: TestClient, session: Session, piece):
    open_response = client.get(f"/pieces/{piece.id}/files/blog.md")
    fingerprint = _fingerprint(open_response.text)

    saved = client.post(f"/pieces/{piece.id}/files/blog.md",
                        data={"text": "# Draft\n\nfirst words", "fingerprint": fingerprint})

    assert saved.status_code == 200
    assert "Saved" in saved.text
    folder = workspace.piece_folder(session, piece)
    assert (folder / "blog.md").read_text(encoding="utf-8") == "# Draft\n\nfirst words"


def test_a_session_writing_underneath_you_is_caught(client: TestClient, session: Session, piece):
    fingerprint = _fingerprint(client.get(f"/pieces/{piece.id}/files/blog.md").text)
    folder = workspace.ensure_folder(session, piece)
    (folder / "blog.md").write_text("written in the terminal", encoding="utf-8")

    response = client.post(f"/pieces/{piece.id}/files/blog.md",
                           data={"text": "written in the browser", "fingerprint": fingerprint})

    assert "changed on disk" in response.text
    assert "Save anyway" in response.text and "Reload from disk" in response.text
    assert (folder / "blog.md").read_text(encoding="utf-8") == "written in the terminal"

    forced = client.post(f"/pieces/{piece.id}/files/blog.md",
                         data={"text": "written in the browser",
                               "fingerprint": _fingerprint(response.text), "force": "true"})
    assert "Saved" in forced.text
    assert (folder / "blog.md").read_text(encoding="utf-8") == "written in the browser"


def test_other_files_in_the_folder_become_tabs(client: TestClient, session: Session, piece):
    folder = workspace.ensure_folder(session, piece)
    (folder / "spec.md").write_text("layout", encoding="utf-8")
    workspace.write_brief(session, piece)

    page = client.get(f"/pieces/{piece.id}").text
    assert "spec.md" in page and "brief.md" in page


def test_the_brief_is_read_only(client: TestClient, session: Session, piece):
    workspace.write_brief(session, piece)

    opened = client.get(f"/pieces/{piece.id}/files/brief.md")
    assert "readonly" in opened.text
    assert "cannot be edited here" in opened.text

    refused = client.post(f"/pieces/{piece.id}/files/brief.md",
                          data={"text": "nonsense", "fingerprint": "whatever"})
    assert refused.status_code == 400


def test_paths_outside_the_folder_are_refused(client: TestClient, piece):
    assert client.get(f"/pieces/{piece.id}/files/..%2Fsecrets.md").status_code in (400, 404)


def test_unknown_piece_is_a_404(client: TestClient):
    assert client.get("/pieces/999").status_code == 404


def _fingerprint(html: str) -> str:
    """Pull the hidden fingerprint out of the rendered editor."""
    marker = 'name="fingerprint" value="'
    start = html.index(marker) + len(marker)
    return html[start:html.index('"', start)]
