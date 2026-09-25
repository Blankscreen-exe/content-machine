"""Starter material: files for a new workspace, and the text a new brand or mode begins with.

`cm init` copies the standing rules a terminal session reads and the skills for jobs that
repeat into the workspace. Files are copied once and then belong to you — `cm init` never
overwrites a file that already exists unless told to.

`cm/starter/brand/` holds the templates a new brand's voice and profile, and a new mode's
description, start from. They are placeholders in square brackets, never a real brand.

`cm/starter/video/` is the video toolchain: the npm packages, pinned by a lockfile, go in
the workspace root, so every piece folder beneath it finds them; the example brand kit
goes in `video/example-kit/`, for a real brand's kit to start from.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .settings import get_settings

STARTER = Path(__file__).resolve().parent / "starter"

# Where each part of the starter goes. Skills live in `.claude/skills/` in the workspace
# because that is where Claude Code looks; in the package they are a plain folder so no
# packaging tool treats them as hidden.
LAYOUT = {
    "CLAUDE.md": "CLAUDE.md",
    "skills": ".claude/skills",
    "video/package.json": "package.json",
    "video/package-lock.json": "package-lock.json",
    "video/.npmrc": ".npmrc",
    "video/kit": "video/example-kit",
}

BRAND_TEMPLATES = STARTER / "brand"
BRAND_NAME_PLACEHOLDER = "[Brand name]"


def _files(source: Path, target: Path) -> list[tuple[Path, Path]]:
    """Pairs of (starter file, workspace destination) for one entry of LAYOUT."""
    if source.is_file():
        return [(source, target)]
    return [(path, target / path.relative_to(source))
            for path in sorted(source.rglob("*")) if path.is_file()]


def init_workspace(force: bool = False) -> list[Path]:
    """Create the workspace folders and copy in the starter files. Returns what was written."""
    settings = get_settings()
    settings.content_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for source_name, target_name in LAYOUT.items():
        for source, destination in _files(STARTER / source_name, settings.workspace / target_name):
            if destination.exists() and not force:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            written.append(destination)
    return written


def brand_starter(name: str) -> dict[str, str]:
    """The voice and profile a new brand starts with, headed with its name."""
    return {field: (BRAND_TEMPLATES / f"{field}.md").read_text(encoding="utf-8")
            .replace(BRAND_NAME_PLACEHOLDER, name)
            for field in ("voice", "profile")}


def mode_starter() -> str:
    """The description a new mode starts with: the questions a mode has to answer."""
    return (BRAND_TEMPLATES / "mode.md").read_text(encoding="utf-8")
