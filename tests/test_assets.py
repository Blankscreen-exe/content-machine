"""A piece's assets: what is stored, what is refused, and that nothing is lost on the way."""
from __future__ import annotations

import io
import os
from base64 import b64decode

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import assets, crud, desktop, workspace
from cm.app import create_app
from cm.database import get_session
from cm.settings import get_settings
from helpers import type_id

TEST_TOKEN = os.environ["CM_TOKEN"]      # set by conftest before anything is imported

# A 1x1 PNG, so these tests need no image library.
PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture(name="piece")
def piece_fixture(session: Session, brand):
    return crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A piece")


def _assets_folder(session: Session, piece):
    return assets.folder_of(workspace.piece_folder(session, piece))


# --- pasting into the editor -------------------------------------------------------------

def test_a_pasted_image_returns_a_relative_path(client: TestClient, session: Session, piece):
    response = client.post(f"/pieces/{piece.id}/assets",
                           files={"file": ("Coincidence Meme.png", PNG, "image/png")})

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "assets/coincidence-meme.png"      # the markdown stays portable
    assert body["url"] == f"/pieces/{piece.id}/assets/coincidence-meme.png"
    assert (_assets_folder(session, piece) / "coincidence-meme.png").read_bytes() == PNG


def test_only_images_can_be_pasted_into_a_draft(client: TestClient, piece):
    response = client.post(f"/pieces/{piece.id}/assets",
                           files={"file": ("carousel.pdf", b"%PDF-1.7", "application/pdf")})
    assert response.status_code == 400
    assert "cannot be stored here" in response.json()["error"]


def test_a_second_file_with_the_same_name_does_not_overwrite(client: TestClient, piece):
    first = client.post(f"/pieces/{piece.id}/assets", files={"file": ("meme.png", PNG, "image/png")})
    second = client.post(f"/pieces/{piece.id}/assets", files={"file": ("meme.png", PNG, "image/png")})
    assert (first.json()["name"], second.json()["name"]) == ("meme.png", "meme-2.png")


# --- the rules every upload follows ----------------------------------------------------------

def test_types_outside_the_list_are_refused(tmp_path):
    for name in ("page.html", "logo.svg", "notes.txt", "no-extension"):
        with pytest.raises(assets.BadAsset, match="cannot be stored here"):
            assets.save(tmp_path, name, io.BytesIO(b"x"))


def test_each_type_has_its_own_size_limit(tmp_path, monkeypatch):
    monkeypatch.setitem(assets.LIMITS, ".pdf", 10)
    with pytest.raises(assets.BadAsset, match="limited to"):
        assets.save(tmp_path, "carousel.pdf", io.BytesIO(b"x" * 11))
    assert assets.save(tmp_path, "cover.png", io.BytesIO(PNG)) == "cover.png"   # images unaffected


def test_a_refused_upload_leaves_nothing_behind(tmp_path, monkeypatch):
    monkeypatch.setitem(assets.LIMITS, ".psd", 10)
    monkeypatch.setattr(assets, "CHUNK", 4)                   # so it fails part-way through
    with pytest.raises(assets.BadAsset):
        assets.save(tmp_path, "working.psd", io.BytesIO(b"x" * 40))
    assert list(tmp_path.iterdir()) == []                     # no half-written file


def test_an_empty_upload_is_refused(tmp_path):
    with pytest.raises(assets.BadAsset, match="empty"):
        assets.save(tmp_path, "cover.png", io.BytesIO(b""))


def test_only_stored_types_are_listed_or_served(client: TestClient, session: Session, piece):
    folder = _assets_folder(session, piece)
    folder.mkdir(parents=True)
    (folder / "cover.png").write_bytes(PNG)
    (folder / "page.html").write_text("<script>alert(1)</script>", encoding="utf-8")

    assert [a.name for a in assets.listing(folder)] == ["cover.png"]
    assert client.get(f"/pieces/{piece.id}/assets/page.html").status_code == 404
    assert client.get(f"/pieces/{piece.id}/assets/cover.png").content == PNG


def test_serving_cannot_escape_the_assets_folder(client: TestClient, session: Session, piece):
    folder = workspace.ensure_folder(session, piece)
    (folder / "brief.md").write_text("not an asset", encoding="utf-8")
    assert client.get(f"/pieces/{piece.id}/assets/..%2Fbrief.md").status_code in (400, 404)
    assert client.get(f"/pieces/{piece.id}/assets/brief.md").status_code == 404


# --- the Assets panel ----------------------------------------------------------------------

def test_several_files_can_be_added_at_once(client: TestClient, session: Session, piece):
    response = client.post(f"/pieces/{piece.id}/assets/files", files=[
        ("uploads", ("Cover.png", PNG, "image/png")),
        ("uploads", ("Carousel.pdf", b"%PDF-1.7 slides", "application/pdf")),
        ("uploads", ("Working File.psd", b"8BPS layers", "image/vnd.adobe.photoshop")),
    ])

    assert response.status_code == 200
    assert "Added cover.png, carousel.pdf, working-file.psd." in response.text
    assert sorted(p.name for p in _assets_folder(session, piece).iterdir()) == [
        "carousel.pdf", "cover.png", "working-file.psd"]
    assert ">PDF</a>" in response.text and ">PSD</a>" in response.text   # file cards, not thumbnails


def test_one_wrong_file_does_not_stop_the_others(client: TestClient, session: Session, piece):
    response = client.post(f"/pieces/{piece.id}/assets/files", files=[
        ("uploads", ("notes.txt", b"hello", "text/plain")),
        ("uploads", ("cover.png", PNG, "image/png")),
    ])
    assert "Added cover.png." in response.text
    assert "notes.txt: .txt cannot be stored here" in response.text
    assert [p.name for p in _assets_folder(session, piece).iterdir()] == ["cover.png"]


def test_deleting_an_asset_moves_it_to_the_trash(client: TestClient, session: Session, piece, workspace_dir):
    client.post(f"/pieces/{piece.id}/assets/files", files=[("uploads", ("cover.png", PNG, "image/png"))])

    response = client.post(f"/pieces/{piece.id}/assets/cover.png/delete")

    assert response.status_code == 200
    # relative to the workspace: the panel already shows the full folder, and the sidebar is narrow
    page = response.text
    start = page.index('<p class="saved">')
    said = page[start:page.index("</p>", start)]
    assert "Moved cover.png to trash" in said and str(workspace_dir) not in said
    assert not (_assets_folder(session, piece) / "cover.png").exists()
    trashed = list((workspace_dir / "trash").rglob("cover.png"))
    assert len(trashed) == 1 and trashed[0].read_bytes() == PNG
    assert trashed[0].parent.name == "assets"


def test_the_piece_page_shows_the_panel_and_loads_the_editor(client: TestClient, piece):
    page = client.get(f"/pieces/{piece.id}").text

    assert 'id="assets"' in page and 'name="uploads" multiple' in page
    assert 'accept=".gif,.jpeg,.jpg,.m4a,.mp3,.mp4,.pdf,.png,.psd,.wav,.webm,.webp"' in page
    assert "/static/vendor/toastui-editor-all.min.js" in page   # the self-contained build
    assert f'data-upload-url="/pieces/{piece.id}/assets"' in page
    assert "https://" not in page and "http://" not in page     # everything is local


def test_open_folder_is_offered_only_on_this_machine(session: Session, piece, monkeypatch):
    opened = []
    monkeypatch.setattr(desktop, "open_folder", lambda path: opened.append(path))
    app = create_app(run_migrations=False)
    app.dependency_overrides[get_session] = lambda: session

    with TestClient(app, cookies={"cm_token": TEST_TOKEN}, client=("192.168.1.20", 50000)) as remote:
        assert "Open folder" not in remote.get(f"/pieces/{piece.id}").text
        refused = remote.post(f"/pieces/{piece.id}/assets/open").text
        assert "only be opened on the machine running the app" in refused
    with TestClient(app, cookies={"cm_token": TEST_TOKEN}, client=("127.0.0.1", 50000)) as local:
        assert "Open folder" in local.get(f"/pieces/{piece.id}").text
        assert "Opened the folder." in local.post(f"/pieces/{piece.id}/assets/open").text
    assert opened == [_assets_folder(session, piece)]


# --- video and audio -----------------------------------------------------------------------

def test_video_and_audio_are_stored_and_played_in_the_panel(client: TestClient, session: Session, piece):
    response = client.post(f"/pieces/{piece.id}/assets/files", files=[
        ("uploads", ("Short.mp4", b"\x00\x00\x00\x18ftypmp42 video", "video/mp4")),
        ("uploads", ("take 1.webm", b"\x1aE\xdf\xa3 voice", "video/webm")),
        ("uploads", ("Theme.mp3", b"ID3 music", "audio/mpeg")),
    ])

    assert "Added short.mp4, take-1.webm, theme.mp3." in response.text
    assert f'<video src="/pieces/{piece.id}/assets/short.mp4" controls preload="metadata">' in response.text
    assert f'<video src="/pieces/{piece.id}/assets/take-1.webm"' in response.text
    assert f'<audio src="/pieces/{piece.id}/assets/theme.mp3" controls preload="metadata">' in response.text


def test_media_is_served_with_its_own_type_whatever_the_system_says(client: TestClient, session: Session,
                                                                     piece, monkeypatch):
    monkeypatch.setattr("mimetypes.guess_type", lambda *args, **kwargs: ("text/plain", None))
    folder = _assets_folder(session, piece)
    folder.mkdir(parents=True)
    for name in ("short.mp4", "take.webm", "theme.mp3", "voice.wav", "voice.m4a"):
        (folder / name).write_bytes(b"media")

    served = {name: client.get(f"/pieces/{piece.id}/assets/{name}").headers["content-type"]
              for name in ("short.mp4", "take.webm", "theme.mp3", "voice.wav", "voice.m4a")}

    assert served == {"short.mp4": "video/mp4", "take.webm": "video/webm", "theme.mp3": "audio/mpeg",
                      "voice.wav": "audio/wav", "voice.m4a": "audio/mp4"}


def test_the_browser_checks_back_so_a_rerendered_draft_is_never_shown_stale(client: TestClient, session: Session, piece):
    folder = _assets_folder(session, piece)
    folder.mkdir(parents=True)
    (folder / "draft.mp4").write_bytes(b"first render")
    assert client.get(f"/pieces/{piece.id}/assets/draft.mp4").headers["cache-control"] == "no-cache"


def test_the_apps_own_scripts_are_checked_back_on_so_an_update_reaches_the_browser(client: TestClient):
    response = client.get("/static/voice.js")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-cache"


def test_every_stored_type_has_a_type_to_be_served_as():
    assert set(assets.MEDIA_TYPES) == set(assets.LIMITS)


def test_a_video_can_be_scrubbed_without_downloading_all_of_it(client: TestClient, session: Session, piece):
    folder = _assets_folder(session, piece)
    folder.mkdir(parents=True)
    (folder / "short.mp4").write_bytes(bytes(range(100)))

    response = client.get(f"/pieces/{piece.id}/assets/short.mp4", headers={"Range": "bytes=10-19"})

    assert response.status_code == 206
    assert response.content == bytes(range(10, 20))


def test_only_images_can_be_pasted_even_now_video_is_stored(client: TestClient, piece):
    response = client.post(f"/pieces/{piece.id}/assets",
                           files={"file": ("short.mp4", b"video", "video/mp4")})
    assert response.status_code == 400
