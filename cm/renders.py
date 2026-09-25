"""Rendering a video piece: from its frames file to a video in its assets.

A draft renders at half size, quickly, to check pacing and look; it replaces the last
draft, `assets/draft.mp4`. A final renders at full size and is kept alongside earlier
ones: `assets/video.mp4`, then `video-2.mp4`, and so on. Rendering never changes the
piece's stage; that stays your call.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from sqlmodel import Session

from . import assets, files, frames, timing, video, workspace
from .models import Piece
from .settings import get_settings

DRAFT_NAME = "draft.mp4"
FINAL_STEM = "video"
DRAFT_SCALE = 0.5


def render_piece(session: Session, piece: Piece, draft: bool = False,
                 on_progress: Callable[[video.Progress], None] = lambda progress: None) -> Path:
    """Render the piece and return where the video was put. Raises video.RenderError, or
    frames.FramesError listing what to fix in the frames file."""
    if not piece.type.video:
        raise video.RenderError(f"{piece.title} is a {piece.type.name}, not a video piece.")
    folder = workspace.piece_folder(session, piece)
    if not files.exists(folder, piece.type.main_file):
        raise video.RenderError(f"{piece.type.main_file} has not been written yet. Save it first.")
    text, _ = files.read(folder, piece.type.main_file)
    line = timing.timeline(frames.parse(text))

    settings = get_settings()
    job = settings.state_dir / "renders" / str(piece.id)
    out = video.render(settings.workspace, folder / "video", job, timing.props(line),
                       scale=DRAFT_SCALE if draft else 1.0, on_progress=on_progress)

    target_dir = assets.folder_of(folder)
    if draft:
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / DRAFT_NAME
        os.replace(out, target)                 # the old draft has no value once replaced
    else:
        target = assets.move(out, target_dir, stem=FINAL_STEM)
    video.clear(job)
    return target
