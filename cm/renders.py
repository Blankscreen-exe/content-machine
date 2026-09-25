"""Rendering a video piece: from its frames file to a video in its assets.

Two steps, so the slow one needs nothing from the database and can run in the background:
`plan` reads the piece and its frames, which is where mistakes are found; `run` renders.

A draft renders at half size, quickly, to check pacing and look; it replaces the last
draft, `assets/draft.mp4`. A final renders at full size and is kept alongside earlier
ones: `assets/video.mp4`, then `video-2.mp4`, and so on. Rendering never changes the
piece's stage; that stays your call.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from . import assets, crud, files, frames, resources, timing, video, voice, workspace
from .models import Piece
from .settings import get_settings

DRAFT_NAME = "draft.mp4"
FINAL_STEM = "video"
DRAFT_SCALE = 0.5


@dataclass(frozen=True)
class Plan:
    """Everything a render needs, read from the piece before it starts."""

    piece_id: int
    video_dir: Path
    assets_dir: Path
    props: dict
    public: dict[str, Path]      # the files it plays, by the name the video loads them as


def plan(session: Session, piece: Piece) -> Plan:
    """Read the piece and its frames. Raises video.RenderError, or frames.FramesError
    listing what to fix in the frames file."""
    if not piece.type.video:
        raise video.RenderError(f"{piece.title} is a {piece.type.name}, not a video piece.")
    folder = workspace.piece_folder(session, piece)
    if not files.exists(folder, piece.type.main_file):
        raise video.RenderError(f"{piece.type.main_file} has not been written yet. Save it first.")
    text, _ = files.read(folder, piece.type.main_file)
    line = timing.timeline(frames.parse(text))
    try:
        mix = voice.read_mix(folder)
    except voice.MixError as exc:
        raise video.RenderError(str(exc)) from exc
    return Plan(piece_id=piece.id, video_dir=folder / "video", assets_dir=assets.folder_of(folder),
                props=timing.props(line) | voice.props(mix, line.fps),
                public=_sound_files(mix, folder, crud.brand_slug(session, piece.brand_id)))


def _sound_files(mix: voice.Mix, folder: Path, brand_slug: str) -> dict[str, Path]:
    """The chosen take and music, by the names the render loads them as."""
    found: dict[str, Path] = {}
    try:
        if mix.take:
            found[voice.public_name("voice", mix.take)] = voice.take_path(folder, mix.take)
        if mix.music:
            found[voice.public_name("music", mix.music)] = resources.path_of(brand_slug, "music", mix.music)
    except FileNotFoundError as exc:
        raise video.RenderError(f"The voice settings use a file that is no longer there ({exc}). "
                                "Choose again on the Voice page.") from exc
    return found


def run(plan: Plan, draft: bool = False,
        on_progress: Callable[[video.Progress], None] = lambda progress: None) -> Path:
    """Render what `plan` describes and return where the video was put."""
    settings = get_settings()
    # A folder of its own, so two renders of one piece never write into each other's files.
    job = settings.state_dir / "renders" / f"{plan.piece_id}-{uuid.uuid4().hex[:8]}"
    out = video.render(settings.workspace, plan.video_dir, job, plan.props,
                       scale=DRAFT_SCALE if draft else 1.0, public=plan.public, on_progress=on_progress)
    try:
        if draft:
            plan.assets_dir.mkdir(parents=True, exist_ok=True)
            target = plan.assets_dir / DRAFT_NAME
            os.replace(out, target)             # the old draft has no value once replaced
        else:
            target = assets.move(out, plan.assets_dir, stem=FINAL_STEM)
    except OSError as exc:
        # On Windows a file being read, such as a draft the browser is playing, cannot be replaced.
        raise video.RenderError(f"The video rendered, but could not be put in {plan.assets_dir} ({exc}). "
                                f"If something has the old one open, close it and render again. "
                                f"The new one is kept at {out}.") from exc
    video.clear(job)
    return target


def render_piece(session: Session, piece: Piece, draft: bool = False,
                 on_progress: Callable[[video.Progress], None] = lambda progress: None) -> Path:
    """Both steps at once, for the command line."""
    return run(plan(session, piece), draft=draft, on_progress=on_progress)
