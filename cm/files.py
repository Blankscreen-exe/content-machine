"""Reading and writing the drafts inside a piece folder.

Two things matter here and are handled in one place so nothing else has to think about
them: a request can only touch files inside its own piece folder, and a save can only
land on the file the editor was given.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# Written by the app before every session; editing it would be pointless.
GENERATED_FILES = {"brief.md"}


class UnsafePath(ValueError):
    """The requested name pointed outside the piece folder."""


class Conflict(RuntimeError):
    """The file changed after it was handed to the editor."""

    def __init__(self, current_text: str, current_digest: str) -> None:
        super().__init__("This file changed on disk since you opened it.")
        self.current_text = current_text
        self.current_digest = current_digest


def digest(text: str) -> str:
    """A short fingerprint of file contents, used to detect edits from elsewhere."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def resolve(folder: Path, name: str) -> Path:
    """The path for `name` inside `folder`, or an error if it escapes."""
    candidate = (folder / name).resolve()
    root = folder.resolve()
    if candidate != root and root not in candidate.parents:
        raise UnsafePath(f"{name!r} is outside the piece folder")
    if candidate.name != name:
        raise UnsafePath(f"{name!r} is not a plain file name")
    return candidate


def list_drafts(folder: Path, main: str) -> list[str]:
    """Markdown files in the folder, the main draft first, generated files last.

    `main` is the piece type's main file: what opens first and is created on the first
    save. Everything else in the folder still shows up as a tab.
    """
    if not folder.is_dir():
        return [main]
    names = sorted(p.name for p in folder.glob("*.md"))
    if main not in names:
        names.insert(0, main)

    def order(name: str) -> tuple[int, str]:
        if name == main:
            return (0, name)
        if name in GENERATED_FILES:
            return (2, name)
        return (1, name)

    return sorted(names, key=order)


def read(folder: Path, name: str) -> tuple[str, str]:
    """Return the text and its fingerprint. A file that does not exist yet reads as empty."""
    path = resolve(folder, name)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return text, digest(text)


def write(folder: Path, name: str, text: str, expected: str, force: bool = False) -> str:
    """Save `text`, unless the file changed since `expected` was taken.

    Returns the new fingerprint. Raises Conflict when someone else — usually a terminal
    session — wrote to the file in the meantime.
    """
    path = resolve(folder, name)
    current, current_digest = read(folder, name)
    if not force and current_digest != expected:
        raise Conflict(current, current_digest)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return digest(text)


def is_editable(name: str) -> bool:
    return name not in GENERATED_FILES
