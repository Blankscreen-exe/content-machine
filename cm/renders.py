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

from . import assets, files, frames, timing, video, workspace
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
    return Plan(piece_id=piece.id, video_dir=folder / "video", assets_dir=assets.folder_of(folder),
                props=timing.props(line))


def run(plan: Plan, draft: bool = False,
        on_progress: Callable[[video.Progress], None] = lambda progress: None) -> Path:
    """Render what `plan` describes and return where the video was put."""
    settings = get_settings()
    # A folder of its own, so two renders of one piece never write into each other's files.
    job = settings.state_dir / "renders" / f"{plan.piece_id}-{uuid.uuid4().hex[:8]}"
    out = video.render(settings.workspace, plan.video_dir, job, plan.props,
                       scale=DRAFT_SCALE if draft else 1.0, on_progress=on_progress)
    if draft:
        plan.assets_dir.mkdir(parents=True, exist_ok=True)
        target = plan.assets_dir / DRAFT_NAME
        os.replace(out, target)                 # the old draft has no value once replaced
    else:
        target = assets.move(out, plan.assets_dir, stem=FINAL_STEM)
    video.clear(job)
    return target


def render_piece(session: Session, piece: Piece, draft: bool = False,
                 on_progress: Callable[[video.Progress], None] = lambda progress: None) -> Path:
    """Both steps at once, for the command line."""
    return run(plan(session, piece), draft=draft, on_progress=on_progress)
