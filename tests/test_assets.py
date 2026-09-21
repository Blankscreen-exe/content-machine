"""Images pasted into a draft: how they are stored, and what is refused."""
from __future__ import annotations

from base64 import b64decode

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, files, workspace
from cm.settings import get_settings

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
    return crud.create_piece(session, brand_id=brand.id, type="blog", title="A piece")


def test_upload_returns_a_relative_path(client: TestClient, session: Session, piece):
    response = client.post(f"/pieces/{piece.id}/assets",
                           files={"file": ("Coincidence Meme.png", PNG, "image/png")})

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "assets/coincidence-meme.png"      # the markdown stays portable
    assert body["url"] == f"/pieces/{piece.id}/assets/coincidence-meme.png"

    stored = workspace.piece_folder(session, piece) / "assets" / "coincidence-meme.png"
    assert stored.read_bytes() == PNG


def test_a_second_image_with_the_same_name_does_not_overwrite(client: TestClient, piece):
    first = client.post(f"/pieces/{piece.id}/assets", files={"file": ("meme.png", PNG, "image/png")})
    second = client.post(f"/pieces/{piece.id}/assets", files={"file": ("meme.png", PNG, "image/png")})

    assert first.json()["name"] == "meme.png"
    assert second.json()["name"] == "meme-2.png"


def test_non_images_are_refused(client: TestClient, piece):
    response = client.post(f"/pieces/{piece.id}/assets",
                           files={"file": ("notes.txt", b"hello", "text/plain")})

    assert response.status_code == 400
    assert "not an image" in response.json()["error"]


def test_oversized_images_are_refused(client: TestClient, piece, monkeypatch):
    monkeypatch.setattr(files, "MAX_IMAGE_BYTES", 10)

    response = client.post(f"/pieces/{piece.id}/assets",
                           files={"file": ("big.png", PNG, "image/png")})

    assert response.status_code == 400
    assert "limited to" in response.json()["error"]


def test_stored_images_are_served_back(client: TestClient, piece):
    client.post(f"/pieces/{piece.id}/assets", files={"file": ("meme.png", PNG, "image/png")})

    served = client.get(f"/pieces/{piece.id}/assets/meme.png")
    assert served.status_code == 200
    assert served.content == PNG


def test_serving_cannot_escape_the_assets_folder(client: TestClient, session: Session, piece):
    folder = workspace.ensure_folder(session, piece)
    (folder / "brief.md").write_text("not an image", encoding="utf-8")

    assert client.get(f"/pieces/{piece.id}/assets/..%2Fbrief.md").status_code in (400, 404)
    assert client.get(f"/pieces/{piece.id}/assets/brief.md").status_code == 404


def test_the_piece_page_loads_the_editor(client: TestClient, piece):
    page = client.get(f"/pieces/{piece.id}").text

    assert "/static/vendor/toastui-editor-all.min.js" in page   # the self-contained build
    assert "/static/editor.js" in page
    assert f'data-piece-id="{piece.id}"' in page
    assert "https://" not in page and "http://" not in page     # everything is local
