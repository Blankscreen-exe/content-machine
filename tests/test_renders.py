"""Rendering a piece: drafts replace each other, finals are all kept, and nothing is left behind."""
from __future__ import annotations

import io

import pytest
from sqlmodel import Session

from cm import crud, frames, renders, video, voice, workspace
from cm.settings import get_settings
from cm.whisper import Heard
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

    def fake_render(workspace_dir, video_dir, job, props, scale=1.0, public=None, on_progress=None):
        calls.append({"video_dir": video_dir, "job": job, "props": props, "scale": scale, "public": public})
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


def test_each_render_has_a_job_folder_of_its_own(session: Session, short, rendered):
    renders.render_piece(session, short)
    renders.render_piece(session, short)
    first, second = rendered[0]["job"], rendered[1]["job"]
    assert first != second and first.name.startswith(f"{short.id}-") and second.name.startswith(f"{short.id}-")


def test_a_draft_is_half_size_and_replaces_the_last_draft(session: Session, short, rendered):
    renders.render_piece(session, short, draft=True)
    draft = renders.render_piece(session, short, draft=True)

    assert draft.name == "draft.mp4" and draft.read_bytes() == b"render 2"
    assert rendered[1]["scale"] == renders.DRAFT_SCALE
    assert [p.name for p in draft.parent.iterdir()] == ["draft.mp4"]


def test_a_video_that_cannot_be_put_in_place_is_kept_and_said_where(session: Session, short, rendered, monkeypatch):
    def locked(source, target):
        raise PermissionError("the file is in use")
    monkeypatch.setattr(renders.os, "replace", locked)

    with pytest.raises(video.RenderError, match="could not be put in") as caught:
        renders.render_piece(session, short, draft=True)
    kept = rendered[0]["job"] / "out.mp4"
    assert str(kept) in str(caught.value) and kept.read_bytes() == b"render 1"


def test_captions_are_timed_to_the_chosen_take_heard_once(session: Session, short, rendered, monkeypatch):
    folder = workspace.piece_folder(session, short)
    voice.save_take(folder, "take.webm", io.BytesIO(b"voice"))
    monkeypatch.setattr(renders.whisper, "installed", lambda workspace: True)
    monkeypatch.setattr(renders.video, "to_wav", lambda workspace, source, target: target)
    hearings = []

    def hear(workspace, wav):
        hearings.append(wav)
        return [Heard("Hello", 0.5), Heard("there.", 1.0)]
    monkeypatch.setattr(renders.whisper, "transcribe", hear)
    steps = []

    renders.render_piece(session, short, on_progress=lambda p: steps.append(p.step))
    renders.render_piece(session, short)

    assert len(hearings) == 1 and steps[0] == "hearing"          # the second render reuses what was heard
    assert rendered[0]["props"]["scenes"][0]["words"] == [{"text": "Hello", "from": 15, "to": 30},
                                                          {"text": "there.", "from": 30, "to": 60}]


def test_without_whisper_a_render_with_timed_captions_says_how_to_get_it(session: Session, short, monkeypatch):
    voice.save_take(workspace.piece_folder(session, short), "take.webm", io.BytesIO(b"voice"))
    monkeypatch.setattr(renders.whisper, "installed", lambda workspace: False)
    with pytest.raises(video.RenderError, match="Run `cm video setup`"):
        renders.plan(session, short)


def test_with_captions_off_the_take_is_never_heard(session: Session, short, rendered, monkeypatch):
    folder = workspace.piece_folder(session, short)
    (folder / "frames.md").write_text("Captions: off\n" + FRAMES, encoding="utf-8")
    voice.save_take(folder, "take.webm", io.BytesIO(b"voice"))
    monkeypatch.setattr(renders.whisper, "installed", lambda workspace: False)
    renders.render_piece(session, short)
    assert rendered[0]["props"]["scenes"][0]["words"] is None


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
