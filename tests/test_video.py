"""Running Remotion: what a render is given, what it reports, and how it fails."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from cm import video

PROPS = {"fps": 30, "width": 1080, "height": 1920, "total": 3, "captions": True, "scenes": []}


class FakeRemotion:
    """Stands in for the render process: prints `lines`, writes the video unless it fails."""

    def __init__(self, lines: list[str], code: int = 0) -> None:
        self.lines, self.code, self.argv, self.cwd = lines, code, None, None

    def __call__(self, argv, cwd=None, **kwargs):
        self.argv, self.cwd = argv, cwd
        if self.code == 0:
            Path(argv[argv.index("Video") + 1]).write_bytes(b"mp4")
        self.stdout = io.StringIO("".join(line + "\n" for line in self.lines))
        return self

    def wait(self) -> int:
        return self.code


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    (tmp_path / "node_modules" / "remotion").mkdir(parents=True)
    monkeypatch.setattr(video.shutil, "which", lambda name: f"/bin/{name}")
    return tmp_path


@pytest.fixture
def video_dir(workspace):
    folder = workspace / "content" / "acme-co" / "2026-09-25-tidy-desk" / "video"
    folder.mkdir(parents=True)
    (folder / "Video.tsx").write_text("export const Video = () => null;", encoding="utf-8")
    return folder


def _render(monkeypatch, workspace, video_dir, fake, **kwargs):
    monkeypatch.setattr(video.subprocess, "Popen", fake)
    return video.render(workspace, video_dir, workspace / ".cm" / "renders" / "7", PROPS, **kwargs)


def test_a_render_is_given_an_entry_its_props_and_nothing_else(monkeypatch, workspace, video_dir):
    fake = FakeRemotion(["Bundling 50%", "Rendered 3/3", "Encoded 3/3"])
    out = _render(monkeypatch, workspace, video_dir, fake, scale=0.5)

    job = workspace / ".cm" / "renders" / "7"
    assert out == job / "out.mp4" and out.read_bytes() == b"mp4"
    assert json.loads((job / "props.json").read_text(encoding="utf-8")) == PROPS
    entry = (job / "entry.tsx").read_text(encoding="utf-8")
    assert 'from "../../../content/acme-co/2026-09-25-tidy-desk/video/Video"' in entry
    assert 'from "../../../video/props"' in entry and "__VIDEO__" not in entry
    assert (workspace / "video" / "props.ts").read_text(encoding="utf-8").count("export type") == 4
    assert fake.cwd == workspace          # where the packages are
    assert fake.argv[1:9] == ["exec", "--no", "--", "remotion", "render", str(job / "entry.tsx"), "Video", str(out)]
    assert "--scale=0.5" in fake.argv and "--codec=h264" in fake.argv
    assert not any("license" in part for part in fake.argv)      # nothing that reports usage


def test_the_render_gets_copies_of_the_files_it_plays_and_nothing_else(monkeypatch, workspace, video_dir, tmp_path):
    take = tmp_path / "take-3.webm"
    take.write_bytes(b"voice")
    _render(monkeypatch, workspace, video_dir, FakeRemotion([]), public={"voice.webm": take})

    public = workspace / ".cm" / "renders" / "7" / "public"
    assert [p.name for p in public.iterdir()] == ["voice.webm"]
    assert (public / "voice.webm").read_bytes() == b"voice" and take.exists()       # a copy: the take stays


def test_progress_is_passed_on_as_it_comes(monkeypatch, workspace, video_dir):
    seen: list[str] = []
    fake = FakeRemotion(["Bundling 21%", "\x1b[90mCodec h264\x1b[39m", "Rendered 1/3, time remaining: 2s", "Encoded 3/3"])
    _render(monkeypatch, workspace, video_dir, fake, on_progress=lambda p: seen.append(str(p)))
    assert seen == ["Bundling 21%", "Rendering 1 / 3 frames", "Encoding 3 / 3 frames"]


def test_a_failed_render_says_what_remotion_said_and_keeps_its_files(monkeypatch, workspace, video_dir):
    fake = FakeRemotion(["Bundling 100%", "\x1b[31mError: Video is not exported from Video.tsx\x1b[39m"], code=1)
    with pytest.raises(video.RenderError) as caught:
        _render(monkeypatch, workspace, video_dir, fake)
    message = str(caught.value)
    assert "Error: Video is not exported from Video.tsx" in message and "\x1b" not in message
    assert str(workspace / ".cm" / "renders" / "7") in message
    assert (workspace / ".cm" / "renders" / "7" / "entry.tsx").exists()


def test_a_missing_export_is_named_and_stack_frames_are_left_out(monkeypatch, workspace, video_dir):
    fake = FakeRemotion([
        "An error occurred:",
        " Error  A value of `undefined` was passed to the `component` prop. Check the value you are passing.",
        "at node_modules/remotion/dist/esm/index.mjs:1354",
        "1352 \\u2502   return compProps.component;",
        "    at useMemo (node_modules/react-dom/cjs/react-dom-client.production.js:5811)",
    ], code=1)
    with pytest.raises(video.RenderError) as caught:
        _render(monkeypatch, workspace, video_dir, fake)
    message = str(caught.value)
    assert message.startswith("video/Video.tsx does not export a component named `Video`.")
    assert "was passed to the `component` prop" in message
    assert "node_modules" not in message and "compProps" not in message


def test_each_render_starts_from_an_empty_job_folder(monkeypatch, workspace, video_dir):
    stale = workspace / ".cm" / "renders" / "7" / "left-over.mp4"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")
    _render(monkeypatch, workspace, video_dir, FakeRemotion([]))
    assert not stale.exists()


def test_without_the_toolchain_setup_is_suggested(monkeypatch, tmp_path, video_dir):
    (tmp_path / "node_modules" / "remotion").rmdir()
    with pytest.raises(video.RenderError, match="Run `cm video setup` first"):
        _render(monkeypatch, tmp_path, video_dir, FakeRemotion([]))


def test_without_a_video_it_says_what_to_write(monkeypatch, workspace, video_dir):
    (video_dir / "Video.tsx").unlink()
    with pytest.raises(video.RenderError, match="exports `Video`, a component that draws the video"):
        _render(monkeypatch, workspace, video_dir, FakeRemotion([]))


def test_only_progress_lines_are_read_as_progress():
    assert video.parse_progress("Bundling 43%") == video.Progress("bundling", 43, 100)
    assert video.parse_progress("Encoded 12/845") == video.Progress("encoding", 12, 845)
    assert video.parse_progress("Getting composition") is None
