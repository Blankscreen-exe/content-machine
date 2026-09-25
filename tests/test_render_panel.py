"""The Render panel: starting a render from the page, following it, and what it says after."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, render_jobs, renders, video, workspace
from cm.settings import get_settings
from helpers import type_id


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    monkeypatch.setattr(render_jobs, "_jobs", {})
    return tmp_path


@pytest.fixture
def short(session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "youtube short"), title="A short")
    (workspace.ensure_folder(session, piece) / "frames.md").write_text("## Hook (2s)\nScript: Hi.\n", encoding="utf-8")
    return piece


@pytest.fixture
def background(monkeypatch):
    """Holds renders instead of starting them, so a test decides when each one runs."""
    held = []
    monkeypatch.setattr(render_jobs, "_spawn", held.append)
    return held


def _fake_run(result_name: str = "video.mp4", error: str | None = None):
    def run(plan, draft=False, on_progress=lambda p: None):
        on_progress(video.Progress("rendering", 30, 60))
        if error:
            raise video.RenderError(error)
        return plan.assets_dir / result_name
    return run


def test_only_a_video_piece_has_the_panel(client: TestClient, session: Session, short, brand):
    assert 'id="render"' in client.get(f"/pieces/{short.id}").text
    blog = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A post")
    assert 'id="render"' not in client.get(f"/pieces/{blog.id}").text
    assert client.post(f"/pieces/{blog.id}/render").status_code == 400


def test_a_running_render_is_followed_until_it_is_done(client: TestClient, short, background, monkeypatch):
    monkeypatch.setattr(renders, "run", _fake_run())

    started = client.post(f"/pieces/{short.id}/render", data={"draft": "true"}).text
    assert 'hx-trigger="every 1s"' in started and "Draft: Starting" in started

    background.pop()()                                   # the render runs and finishes
    followed = client.get(f"/pieces/{short.id}/render?following=true")

    assert "Rendered <code>assets/video.mp4</code>" in followed.text
    assert "every 1s" not in followed.text               # nothing left to follow
    assert followed.headers["HX-Trigger"] == "assets-changed"


def test_the_assets_panel_redraws_only_when_a_followed_render_finishes(client: TestClient, short, background,
                                                                       monkeypatch):
    monkeypatch.setattr(renders, "run", _fake_run())
    client.post(f"/pieces/{short.id}/render")
    background.pop()()
    # opened afresh later, the panel shows the result but has no reason to redraw anything
    assert "HX-Trigger" not in client.get(f"/pieces/{short.id}/render").headers
    assert 'hx-trigger="assets-changed from:body"' in client.get(f"/pieces/{short.id}").text


def test_a_second_render_waits_for_the_first(client: TestClient, short, background, monkeypatch):
    monkeypatch.setattr(renders, "run", _fake_run())
    client.post(f"/pieces/{short.id}/render")

    second = client.post(f"/pieces/{short.id}/render", data={"draft": "true"}).text

    assert "A final render of this piece is running" in second and len(background) == 1


def test_a_failed_render_shows_what_went_wrong(client: TestClient, short, background, monkeypatch):
    monkeypatch.setattr(renders, "run", _fake_run(error="video/Video.tsx does not export a component named `Video`."))
    client.post(f"/pieces/{short.id}/render")
    background.pop()()

    panel = client.get(f"/pieces/{short.id}/render?following=true")
    assert "does not export a component named `Video`" in panel.text and "Render final" in panel.text
    assert "HX-Trigger" not in panel.headers


def test_frames_that_need_fixing_are_listed_and_nothing_starts(client: TestClient, session: Session, short,
                                                               background):
    (workspace.piece_folder(session, short) / "frames.md").write_text("Captions: maybe\n## Hook\nScript: Hi.",
                                                                      encoding="utf-8")
    panel = client.post(f"/pieces/{short.id}/render").text
    assert "frames.md needs fixing first:" in panel and "Captions: “maybe” should be on or off." in panel
    assert background == []


def test_an_unexpected_error_still_ends_the_render(short, background, monkeypatch, session: Session):
    def broken(plan, draft=False, on_progress=None):
        raise KeyError("scenes")
    monkeypatch.setattr(renders, "run", broken)
    job = render_jobs.start(renders.plan(session, short), draft=False)
    background.pop()()
    assert job.state == "failed" and "KeyError" in job.error and job.finished is not None


def test_the_assets_panel_can_be_fetched_on_its_own(client: TestClient, short):
    panel = client.get(f"/pieces/{short.id}/assets")
    assert panel.status_code == 200 and 'id="assets"' in panel.text
