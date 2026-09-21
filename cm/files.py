"""Reading and writing the drafts inside a piece folder.

Two things matter here and are handled in one place so nothing else has to think about
them: a request can only touch files inside its own piece folder, and a save can only
land on the file the editor was given.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .models import PieceType
from .text import slugify

# What a piece of each type is mainly written in. Everything else in the folder still
# shows up as a tab; this is only what opens first and gets created on the first save.
MAIN_FILE: dict[PieceType, str] = {
    PieceType.blog: "blog.md",
    PieceType.linkedin: "linkedin.md",
    PieceType.x: "x.md",
    PieceType.infographic: "spec.md",
    PieceType.carousel: "spec.md",
    PieceType.quote: "quotes.md",
    PieceType.other: "draft.md",
}

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
    """Markdown files in the folder, the main draft first, generated files last."""
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


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class BadImage(ValueError):
    """The upload was not something we are willing to store."""


def images(folder: Path) -> list[str]:
    assets = folder / "assets"
    if not assets.is_dir():
        return []
    return sorted(p.name for p in assets.iterdir()
                  if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def save_image(folder: Path, filename: str, data: bytes) -> str:
    """Store an image in the piece's `assets/` folder and return its file name.

    The name comes from us, not from the upload: a slug of the original plus a counter if
    it is taken. That removes any question of odd characters or paths in a file name.
    """
    suffix = Path(filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise BadImage(f"{suffix or 'that file type'} is not an image we store "
                       f"({', '.join(sorted(IMAGE_SUFFIXES))})")
    if not data:
        raise BadImage("the file was empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise BadImage(f"images are limited to {MAX_IMAGE_BYTES // (1024 * 1024)} MB")

    assets = folder / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    stem = slugify(Path(filename).stem) or "image"
    name, counter = f"{stem}{suffix}", 2
    while (assets / name).exists():
        name = f"{stem}-{counter}{suffix}"
        counter += 1

    (assets / name).write_bytes(data)
    return name


def image_path(folder: Path, name: str) -> Path:
    """The path of one stored image, or an error if the name points elsewhere."""
    path = resolve(folder / "assets", name)
    if path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file():
        raise UnsafePath(f"{name!r} is not a stored image")
    return path
