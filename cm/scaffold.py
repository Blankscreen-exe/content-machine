"""Starter files for a new workspace.

Everything under `cm/starter/` is copied into the workspace by `cm init`: the standing
rules a terminal session reads, the skills for jobs that repeat, and one dummy brand to
copy from. The starter never contains a real brand; real brands live only in the
workspace. Files are copied once and then belong to you — `cm init` never overwrites a
file that already exists unless told to.
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
    "brands": "brands",
}


def _files(source: Path, target: Path) -> list[tuple[Path, Path]]:
    """Pairs of (starter file, workspace destination) for one entry of LAYOUT."""
    if source.is_file():
        return [(source, target)]
    return [(path, target / path.relative_to(source))
            for path in sorted(source.rglob("*")) if path.is_file()]


def init_workspace(force: bool = False) -> list[Path]:
    """Create the workspace folders and copy in the starter files. Returns what was written."""
    settings = get_settings()
    for folder in (settings.brands_dir, settings.content_dir):
        folder.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for source_name, target_name in LAYOUT.items():
        for source, destination in _files(STARTER / source_name, settings.workspace / target_name):
            if destination.exists() and not force:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            written.append(destination)
    return written
