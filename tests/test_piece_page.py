"""The piece page and its editor, over HTTP."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, desktop, workspace
from cm.app import create_app
from cm.database import get_session
from cm.settings import get_settings
from helpers import type_id


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture(name="piece")
def piece_fixture(session: Session, brand):
    return crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"),
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
    assert "Save anyway" in response.text and "Reload saved version" in response.text
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


def test_the_pane_has_an_unsaved_marker_and_a_count(client: TestClient, piece):
    pane = client.get(f"/pieces/{piece.id}/files/blog.md").text
    assert '<span class="unsaved-marker" hidden>unsaved</span>' in pane
    assert 'class="char-count"' in pane and "data-limit" not in pane     # blogs have no limit
    assert 'data-unsaved="true"' not in pane


def test_a_refused_save_is_still_unsaved(client: TestClient, session: Session, piece):
    fingerprint = _fingerprint(client.get(f"/pieces/{piece.id}/files/blog.md").text)
    (workspace.ensure_folder(session, piece) / "blog.md").write_text("from a session", encoding="utf-8")

    response = client.post(f"/pieces/{piece.id}/files/blog.md",
                           data={"text": "typed here", "fingerprint": fingerprint})

    assert 'data-unsaved="true"' in response.text     # on screen, but not on disk


def test_the_count_carries_the_types_limit(client: TestClient, session: Session, brand):
    post = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "linkedin post"),
                             title="A post")
    assert 'data-limit="3000"' in client.get(f"/pieces/{post.id}").text


def test_open_folder_opens_the_piece_folder_from_this_machine(session: Session, piece, monkeypatch):
    """The drafts are in the piece folder; the Assets panel's button opens assets/ inside it."""
    opened = []
    monkeypatch.setattr(desktop, "open_folder", lambda path: opened.append(path))
    app = create_app(run_migrations=False)
    app.dependency_overrides[get_session] = lambda: session
    cookies = {"cm_token": os.environ["CM_TOKEN"]}

    with TestClient(app, cookies=cookies, client=("192.168.1.20", 50000)) as remote:
        assert "Open folder" not in remote.get(f"/pieces/{piece.id}").text
        refused = remote.post(f"/pieces/{piece.id}/files/open")
        assert "only be opened on the machine running the app" in refused.text

    with TestClient(app, cookies=cookies, client=("127.0.0.1", 50000)) as local:
        page = local.get(f"/pieces/{piece.id}").text
        assert page.count("Open folder") == 2            # the drafts folder, and assets/
        assert f'hx-post="/pieces/{piece.id}/files/open"' in page
        assert "Opened" in local.post(f"/pieces/{piece.id}/files/open").text

    assert opened == [workspace.piece_folder(session, piece)]


def test_opening_the_folder_leaves_the_writing_pane_alone(client: TestClient, piece):
    """It answers with a message, not a new pane: a redrawn pane would lose unsaved typing."""
    response = client.post(f"/pieces/{piece.id}/files/open")
    assert 'id="editor-pane"' not in response.text


def test_the_assets_panel_sits_beside_the_drafts(client: TestClient, piece):
    """Side by side while there is room; the stylesheet stacks them on a narrow window."""
    page = client.get(f"/pieces/{piece.id}").text
    workbench = page[page.index('<div class="workbench">'):page.index("</aside>")]

    assert 'id="editor-pane"' in workbench and 'id="assets"' in workbench
    assert workbench.index('id="editor-pane"') < workbench.index('<aside class="workbench-side">')
    # the publish records follow the drafts, in the same column
    assert 'id="publications"' in workbench
    assert workbench.index('id="publications"') < workbench.index('<aside class="workbench-side">')


def test_the_assets_sidebar_keeps_its_controls_above_the_files(client: TestClient, session: Session,
                                                               piece):
    """There is one drop zone and one folder button, however many files there are."""
    client.post(f"/pieces/{piece.id}/assets/files",
                files=[("uploads", ("cover.png", b"not really a png", "image/png"))])
    page = client.get(f"/pieces/{piece.id}").text
    panel = page[page.index('id="assets"'):page.index("</aside>")]

    assert panel.index("drop-zone") < panel.index("asset-scroll")
