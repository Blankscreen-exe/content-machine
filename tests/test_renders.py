"""Rendering a piece: drafts replace each other, finals are all kept, and nothing is left behind."""
from __future__ import annotations

import pytest
from sqlmodel import Session

from cm import crud, frames, renders, video, workspace
from cm.settings import get_settings
from helpers import type_id

FRAMES = "## Hook (2s)\nScript: Hello there.\n"


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture
def short(session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "youtube short"), title="A short")
    (workspace.ensure_folder(session, piece) / "frames.md").write_text(FRAMES, encoding="utf-8")
    return piece


@pytest.fixture
def rendered(monkeypatch):
    """Stands in for Remotion: writes a video named after the call, and records what it was given."""
    calls = []

    def fake_render(workspace_dir, video_dir, job, props, scale=1.0, on_progress=None):
        calls.append({"video_dir": video_dir, "job": job, "props": props, "scale": scale})
        job.mkdir(parents=True, exist_ok=True)
        out = job / "out.mp4"
        out.write_bytes(f"render {len(calls)}".encode())
        return out

    monkeypatch.setattr(renders.video, "render", fake_render)
    return calls


def test_a_piece_renders_its_frames_timed_and_sized(session: Session, short, rendered):
    renders.render_piece(session, short)
    call = rendered[0]
    assert call["video_dir"] == workspace.piece_folder(session, short) / "video"
    assert call["props"]["total"] == 60 and call["props"]["scenes"][0]["script"] == "Hello there."
    assert call["scale"] == 1.0


def test_finals_are_all_kept_and_the_job_is_cleared(session: Session, short, rendered):
    first = renders.render_piece(session, short)
    second = renders.render_piece(session, short)

    assert (first.name, second.name) == ("video.mp4", "video-2.mp4")
    assert first.read_bytes() == b"render 1" and second.read_bytes() == b"render 2"
    assert not rendered[0]["job"].exists()


def test_a_draft_is_half_size_and_replaces_the_last_draft(session: Session, short, rendered):
    renders.render_piece(session, short, draft=True)
    draft = renders.render_piece(session, short, draft=True)

    assert draft.name == "draft.mp4" and draft.read_bytes() == b"render 2"
    assert rendered[1]["scale"] == renders.DRAFT_SCALE
    assert [p.name for p in draft.parent.iterdir()] == ["draft.mp4"]


def test_frames_that_cannot_be_read_stop_the_render(session: Session, short, rendered):
    (workspace.piece_folder(session, short) / "frames.md").write_text("Format: tall\n## Hook\nScript: Hi.", encoding="utf-8")
    with pytest.raises(frames.FramesError):
        renders.render_piece(session, short)
    assert rendered == []


def test_frames_never_saved_are_not_rendered_from_the_template(session: Session, brand, rendered):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "youtube short"), title="New")
    with pytest.raises(video.RenderError, match="frames.md has not been written yet"):
        renders.render_piece(session, piece)


def test_a_text_piece_is_not_rendered(session: Session, brand, rendered):
    blog = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A post")
    with pytest.raises(video.RenderError, match="not a video piece"):
        renders.render_piece(session, blog)
