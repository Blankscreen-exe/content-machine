"""A brand's resources: each upload lands in the folder its type belongs to, and stays there."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud
from cm.settings import get_settings
from test_assets import PNG


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


def _url(brand, rest: str = "") -> str:
    return f"/manage/brands/{brand.id}/resources{rest}"


def test_images_and_music_go_to_their_own_folders(client: TestClient, brand, workspace_dir):
    response = client.post(_url(brand), files=[
        ("uploads", ("Portrait.png", PNG, "image/png")),
        ("uploads", ("Calm Theme.mp3", b"ID3 music", "audio/mpeg")),
    ])

    assert "Added images/portrait.png, music/calm-theme.mp3." in response.text
    folder = workspace_dir / "resources" / brand.slug
    assert (folder / "images" / "portrait.png").read_bytes() == PNG
    assert (folder / "music" / "calm-theme.mp3").exists()
    assert f'<audio src="{_url(brand, "/music/calm-theme.mp3")}"' in response.text


def test_anything_else_is_refused_with_what_is_accepted(client: TestClient, brand, workspace_dir):
    response = client.post(_url(brand), files=[
        ("uploads", ("carousel.pdf", b"%PDF", "application/pdf")),
        ("uploads", ("short.mp4", b"video", "video/mp4")),
    ])
    assert "carousel.pdf: .pdf is not a brand resource (images:" in response.text
    assert "short.mp4: .mp4 is not a brand resource" in response.text
    assert not (workspace_dir / "resources").exists()


def test_resources_are_served_only_from_their_own_kind(client: TestClient, brand):
    client.post(_url(brand), files=[("uploads", ("portrait.png", PNG, "image/png"))])

    served = client.get(_url(brand, "/images/portrait.png"))
    assert served.content == PNG and served.headers["content-type"] == "image/png"
    assert client.get(_url(brand, "/music/portrait.png")).status_code == 404
    assert client.get(_url(brand, "/kit/portrait.png")).status_code == 404
    assert client.get(_url(brand, "/images/..%2F..%2Fcontent.db")).status_code in (400, 404)


def test_each_brand_sees_only_its_own(client: TestClient, session: Session, brand):
    client.post(_url(brand), files=[("uploads", ("portrait.png", PNG, "image/png"))])
    other = crud.create_brand(session, "acme-co", "Acme Co")

    assert client.get(_url(other, "/images/portrait.png")).status_code == 404
    assert "No images yet." in client.get(f"/manage/brands/{other.id}").text


def test_deleting_moves_a_resource_to_the_trash(client: TestClient, brand, workspace_dir):
    client.post(_url(brand), files=[("uploads", ("theme.mp3", b"ID3", "audio/mpeg"))])

    response = client.post(_url(brand, "/music/theme.mp3/delete"))

    assert f"Moved music/theme.mp3 to trash/{brand.slug}/resources/music/." in response.text
    assert (workspace_dir / "trash" / brand.slug / "resources" / "music" / "theme.mp3").exists()
    assert not (workspace_dir / "resources" / brand.slug / "music" / "theme.mp3").exists()


def test_the_brand_page_shows_the_panel_and_where_the_kit_lives(client: TestClient, brand, workspace_dir):
    page = client.get(f"/manage/brands/{brand.id}").text
    assert 'id="resources"' in page and "No images yet." in page and "No music yet." in page
    assert str(workspace_dir / "resources" / brand.slug / "kit") in page


def test_the_folder_is_only_opened_from_this_machine(client: TestClient, brand):
    # the test client is not on this machine's loopback address
    response = client.post(_url(brand, "/open"))
    assert "can only be opened on the machine running the app" in response.text
