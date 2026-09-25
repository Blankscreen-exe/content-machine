"""Running Remotion: the one module that knows how a video is actually rendered.

A render is a job folder under the workspace's `.cm/renders/`, holding what this render
needs and nothing else:

    entry.tsx     registers the piece's video with the size, frame rate and length given
    props.json    what the video is handed: its scenes and settings (timing.py)
    public/       copies of the files the render plays: the chosen voice take and music
    out.mp4       the result, until the caller moves it to where it belongs

It sits inside the workspace so the entry finds the npm packages at the workspace root.
Swapping Remotion for another renderer means changing this module and remotion/.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

CONTRACT = Path(__file__).resolve().parent / "remotion"
# The component a piece's video exports, in the file it exports it from.
VIDEO_FILE = "Video.tsx"
COMPOSITION = "Video"
# Lines of Remotion's output kept to explain a failed render.
TAIL = 25

ANSI = re.compile(r"\x1b\[[0-9;]*m")
BUNDLING = re.compile(r"^Bundling (\d+)%")
FRAMES = re.compile(r"^(Rendered|Encoded) (\d+)/(\d+)")
# Stack frames and quoted source lines: where inside Remotion or React it failed, which
# buries what failed. Remotion's own message comes before them.
NOISE = re.compile(r"^\s*(at |\d+ (│|\\u2502))")
# Failures whose cause Remotion's own words do not name, said in terms of the piece.
HINTS = {
    "was passed to the `component` prop": f"video/{VIDEO_FILE} does not export a component named "
                                          f"`{COMPOSITION}`. Export it by that name.",
}


class RenderError(RuntimeError):
    """The render could not be done; the message says why and what to do."""


@dataclass(frozen=True)
class Progress:
    step: str           # "bundling", "rendering" or "encoding"
    done: int
    total: int

    def __str__(self) -> str:
        if self.step == "bundling":
            return f"Bundling {self.done}%"
        return f"{self.step.capitalize()} {self.done} / {self.total} frames"


def write_contract(workspace: Path) -> Path:
    """Put the props a video is handed, as TypeScript, where a piece's video can import them."""
    target = workspace / "video" / "props.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CONTRACT / "props.ts", target)
    return target


def render(workspace: Path, video_dir: Path, job: Path, props: dict, scale: float = 1.0,
           public: dict[str, Path] | None = None,
           on_progress: Callable[[Progress], None] = lambda progress: None) -> Path:
    """Render the video in `video_dir` with `props`, in the job folder `job`. `public` names
    the files it may load, by the name it loads them as. Returns the rendered file, still
    in the job folder."""
    if not (workspace / "node_modules" / "remotion").is_dir():
        raise RenderError("The video toolchain is not installed. Run `cm video setup` first.")
    video = video_dir / VIDEO_FILE
    if not video.is_file():
        raise RenderError(f"There is no {video}. It exports `{COMPOSITION}`, a component that "
                          "draws the video with the brand's kit; write it first.")
    npm = shutil.which("npm")
    if not npm:
        raise RenderError("npm is not on PATH. It comes with Node: https://nodejs.org")

    _fresh(job)
    contract = write_contract(workspace)
    entry = (CONTRACT / "entry.tsx").read_text(encoding="utf-8")
    entry = (entry.replace("__VIDEO__", _import_path(job, video))
                  .replace("__PROPS__", _import_path(job, contract)))
    (job / "entry.tsx").write_text(entry, encoding="utf-8")
    (job / "props.json").write_text(json.dumps(props, indent=1), encoding="utf-8")
    (job / "public").mkdir()
    # copies, so the render sees these files and nothing else of the workspace
    for name, source in (public or {}).items():
        shutil.copyfile(source, job / "public" / name)
    out = job / "out.mp4"

    argv = [npm, "exec", "--no", "--", "remotion", "render", str(job / "entry.tsx"), COMPOSITION, str(out),
            f"--props={job / 'props.json'}", f"--public-dir={job / 'public'}", "--codec=h264",
            f"--scale={scale}"]
    try:
        _run(argv, workspace, on_progress)
    except RenderError as exc:
        raise RenderError(f"{exc}\n\nEverything this render used is kept in {job}.") from exc
    if not out.is_file():
        raise RenderError("Remotion finished without writing a video. Run it again; if it keeps "
                          "happening, the output above the last render says why.")
    return out


def clear(job: Path) -> None:
    """Remove a job folder once its video has been moved to where it belongs."""
    shutil.rmtree(job, ignore_errors=True)


def parse_progress(line: str) -> Progress | None:
    """Read one line of Remotion's output as progress, if it is any."""
    line = ANSI.sub("", line).strip()
    if match := BUNDLING.match(line):
        return Progress("bundling", int(match.group(1)), 100)
    if match := FRAMES.match(line):
        step = "rendering" if match.group(1) == "Rendered" else "encoding"
        return Progress(step, int(match.group(2)), int(match.group(3)))
    return None


def _run(argv: list[str], cwd: Path, on_progress: Callable[[Progress], None]) -> None:
    """Run the render, passing on progress as it comes and keeping the last lines to
    explain a failure."""
    tail: deque[str] = deque(maxlen=TAIL)
    try:
        process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RenderError(f"Could not start the render: {exc}") from exc
    for line in process.stdout:
        if progress := parse_progress(line):
            on_progress(progress)
        elif line.strip() and not NOISE.match(ANSI.sub("", line)):
            tail.append(ANSI.sub("", line.rstrip()))
    if process.wait() != 0:
        said = "\n".join(tail)
        hints = [hint for clue, hint in HINTS.items() if clue in said]
        raise RenderError("\n\n".join([*hints, "The render failed. Remotion said:\n" + said]))


def _fresh(job: Path) -> None:
    """An empty job folder: whatever an earlier render left there is not this render's."""
    if job.exists():
        shutil.rmtree(job)
    job.mkdir(parents=True)


def _import_path(job: Path, target: Path) -> str:
    """`target` as an import from the entry in `job`: relative, forward slashes, no extension."""
    relative = Path(os.path.relpath(target.with_suffix(""), job)).as_posix()
    return relative if relative.startswith(".") else f"./{relative}"
