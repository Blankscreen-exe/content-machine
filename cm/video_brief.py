"""The Video section of a video piece's brief: what a session needs to build its video.

Where the video goes and what it is handed, where the brand's kit and images are, and
the frames as the app reads them, problems included, so the session starts from the same
reading the render will. Import paths are given ready to paste, relative to the video.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import assets, files, frames, resources, timing, video
from .models import Piece
from .settings import get_settings


def section(piece: Piece, folder: Path, brand_slug: str) -> list[str]:
    settings = get_settings()
    video_dir = folder / "video"
    contract = video.write_contract(settings.workspace)
    kit = resources.kit_folder(brand_slug)
    images_dir = resources.folder(brand_slug, "images")
    images = assets.listing(images_dir)

    lines = ["", "## Video", "",
             f"Build it with the video skill: `video/{video.VIDEO_FILE}` in this folder, exporting "
             f"`{video.COMPOSITION}`, drawn with the brand's kit.", ""]
    lines += _frames(piece, folder)
    lines += ["", f"- Props it is handed: `import type {{ VideoProps, Scene }} from \"{_relative(video_dir, contract)}\";`"]
    if (kit / "index.ts").is_file():
        lines.append(f"- Brand kit: `import {{ ... }} from \"{_relative(video_dir, kit)}\";` ({kit})")
    else:
        example = settings.workspace / "video" / "example-kit"
        lines.append(f"- Brand kit: none yet at {kit}. Ask me before starting one; the example kit "
                     f"to start from is {example}.")
    if images:
        names = ", ".join(f"`{image.name}`" for image in images)
        lines.append(f"- Brand images, imported by path (`import image from \"{_relative(video_dir, images_dir)}"
                     f"/{images[0].name}\";`): {names}")
    lines.append(f"- Render a draft to check it: `cm render {piece.id} --draft`")
    return lines


def _frames(piece: Piece, folder: Path) -> list[str]:
    name = piece.type.main_file
    if not files.exists(folder, name):
        return [f"{name} has not been written yet. There is nothing to build until it is."]
    text, _ = files.read(folder, name)
    try:
        read = frames.parse(text)
    except frames.FramesError as exc:
        return [f"{name} cannot be read as frames yet; the render will refuse it until these are fixed:",
                *(f"- {problem}" for problem in exc.problems)]
    line = timing.timeline(read)
    return [f"{name} reads as: {read.summary()} · about {round(line.seconds)}s. The frames, "
            "in order, with where each sits on the timeline:", "",
            *(f"{i}. {scene.frame.title or 'untitled'}: frames {scene.start}–{scene.start + scene.length - 1}"
              f", script said over the first {scene.speech}"
              for i, scene in enumerate(line.scenes, start=1))]


def _relative(start: Path, target: Path) -> str:
    """`target` as an import from a file in `start`: relative, forward slashes, no extension."""
    return Path(os.path.relpath(target.with_suffix("") if target.suffix == ".ts" else target, start)).as_posix()
