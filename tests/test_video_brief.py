"""What a session building a video is told: its frames as the render reads them, and where things are."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, resources, workspace
from cm.settings import get_settings
from helpers import type_id
from test_assets import PNG


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture
def short(session: Session, brand):
    return crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "youtube short"), title="A short")


def _brief(session: Session, piece, frames_text: str | None = None) -> str:
    if frames_text is not None:
        (workspace.ensure_folder(session, piece) / "frames.md").write_text(frames_text, encoding="utf-8")
    return workspace.write_brief(session, piece).read_text(encoding="utf-8")


def test_the_brief_gives_the_frames_on_their_timeline(session: Session, short):
    brief = _brief(session, short, "## Hook (2s)\nScript: Hello there.\n## Close\nScript: Bye.\n")

    assert "## Video" in brief and "`video/Video.tsx` in this folder, exporting `Video`" in brief
    assert "frames.md reads as: 2 frames · vertical 1080×1920 · captions on · about 4s." in brief
    assert "1. Hook: frames 0–59, script said over the first 24" in brief
    assert "2. Close: frames 60–104" in brief


def test_the_brief_passes_on_what_stops_the_render(session: Session, short):
    brief = _brief(session, short, "Format: tall\n## Hook\nScript: Hi.")
    assert "the render will refuse it until these are fixed:" in brief
    assert "- Format: “tall” is not one of vertical, square, portrait, landscape." in brief


def test_the_brief_says_when_there_are_no_frames_yet(session: Session, short):
    assert "frames.md has not been written yet." in _brief(session, short)


def test_imports_are_ready_to_paste_from_the_video(session: Session, short, workspace_dir):
    brief = _brief(session, short, "## Hook\nScript: Hi.")
    assert 'import type { VideoProps, Scene } from "../../../../video/props";' in brief
    assert (workspace_dir / "video" / "props.ts").is_file()          # written for the session to read


def test_without_a_kit_the_session_is_told_to_ask_first(session: Session, short, brand, workspace_dir):
    brief = _brief(session, short, "## Hook\nScript: Hi.")
    assert f"Brand kit: none yet at {resources.kit_folder(brand.slug)}. Ask me before starting one" in brief
    assert str(workspace_dir / "video" / "example-kit") in brief


def test_with_a_kit_and_images_the_imports_are_given(session: Session, short, brand):
    kit = resources.kit_folder(brand.slug)
    kit.mkdir(parents=True)
    (kit / "index.ts").write_text("export {};", encoding="utf-8")
    images = resources.folder(brand.slug, "images")
    images.mkdir(parents=True)
    (images / "portrait.png").write_bytes(PNG)

    brief = _brief(session, short, "## Hook\nScript: Hi.")

    assert f'from "../../../../resources/{brand.slug}/kit";' in brief
    assert f'import image from "../../../../resources/{brand.slug}/images/portrait.png";' in brief


def test_a_text_piece_has_no_video_section(session: Session, brand):
    blog = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A post")
    assert "## Video" not in _brief(session, blog)


# --- the Build video button ------------------------------------------------------------------

def test_build_video_opens_a_session_with_the_video_skill(local_client: TestClient, session: Session, short,
                                                          launches):
    _brief(session, short, "## Hook\nScript: Hi.")
    response = local_client.post(f"/pieces/{short.id}/build-video")

    assert "Session opened" in response.text
    assert "use the video skill" in launches[0]["command"][1]
    assert "## Video" in (launches[0]["cwd"] / "brief.md").read_text(encoding="utf-8")


def test_build_video_only_starts_on_this_machine(client: TestClient, short, launches):
    assert "only be started on the machine running the app" in client.post(f"/pieces/{short.id}/build-video").text
    assert launches == []


def test_build_video_is_only_for_video_pieces(local_client: TestClient, session: Session, brand, launches):
    blog = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A post")
    assert local_client.post(f"/pieces/{blog.id}/build-video").status_code == 400
