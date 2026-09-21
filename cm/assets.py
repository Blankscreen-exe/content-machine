"""The files that go with a piece: images, PDFs and Photoshop files in its `assets/` folder.

Uploads come from the browser, which may be on another device than the one running the
app, so this is how a finished image gets into the piece folder. Three rules:

- Only these types are stored or served. A file the browser would run as a page, such as
  HTML or SVG, is never handed back from the app's own address.
- A file is written under a temporary name and renamed once it is complete, so an upload
  that fails or runs over its limit leaves nothing behind.
- The stored name comes from the app, not the upload: a slug of the original, numbered if
  taken, so odd characters or paths in a file name never reach the disk.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .files import resolve
from .text import slugify

MB = 1024 * 1024

# What may be stored, and how large each may be.
LIMITS = {
    ".png": 10 * MB, ".jpg": 10 * MB, ".jpeg": 10 * MB, ".gif": 10 * MB, ".webp": 10 * MB,
    ".pdf": 50 * MB,           # a LinkedIn carousel is posted as a PDF
    ".psd": 200 * MB,          # the working file, kept with the piece
}
# Shown as thumbnails, and the only kind that can be pasted into a draft.
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
IMAGE_LIMITS = {suffix: LIMITS[suffix] for suffix in IMAGE_SUFFIXES}

PARTIAL = ".part"              # an upload still being written
CHUNK = MB


class BadAsset(ValueError):
    """The upload was not something we are willing to store; the message says why."""


@dataclass(frozen=True)
class Asset:
    name: str
    size: int

    @property
    def is_image(self) -> bool:
        return Path(self.name).suffix.lower() in IMAGE_SUFFIXES

    @property
    def kind(self) -> str:
        """What to call it on a file card: PDF, PSD..."""
        return Path(self.name).suffix.lstrip(".").upper()


def folder_of(piece_folder: Path) -> Path:
    return piece_folder / "assets"


def listing(piece_folder: Path) -> list[Asset]:
    """The stored files, by name. Anything else in the folder is not shown or served."""
    folder = folder_of(piece_folder)
    if not folder.is_dir():
        return []
    return sorted((Asset(p.name, p.stat().st_size) for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in LIMITS),
                  key=lambda asset: asset.name.lower())


def save(piece_folder: Path, filename: str, source: BinaryIO, limits: dict[str, int] = LIMITS) -> str:
    """Store one upload and return its file name. `limits` narrows what is accepted."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in limits:
        raise BadAsset(f"{filename or 'That file'}: {suffix or 'files without an extension'} "
                       f"cannot be stored here ({', '.join(sorted(limits))})")

    folder = folder_of(piece_folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = _free_name(folder, slugify(Path(filename).stem) or "file", suffix)
    partial = folder / (name + PARTIAL)

    written = 0
    try:
        with partial.open("wb") as out:
            while chunk := source.read(CHUNK):
                written += len(chunk)
                if written > limits[suffix]:
                    raise BadAsset(f"{filename}: {suffix} files are limited to "
                                   f"{limits[suffix] // MB} MB")
                out.write(chunk)
        if written == 0:
            raise BadAsset(f"{filename}: the file was empty")
        partial.rename(folder / name)
    finally:
        partial.unlink(missing_ok=True)
    return name


def path_of(piece_folder: Path, name: str) -> Path:
    """The path of one stored file, or an error if the name points anywhere else."""
    path = resolve(folder_of(piece_folder), name)
    if path.suffix.lower() not in LIMITS or not path.is_file():
        raise FileNotFoundError(f"{name!r} is not a stored asset")
    return path


def move(path: Path, target_dir: Path) -> Path:
    """Move a stored file into `target_dir`, numbered if the name is taken there."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _free_name(target_dir, path.stem, path.suffix)
    path.rename(target)             # same workspace, so it moves whole or not at all
    return target


def _free_name(folder: Path, stem: str, suffix: str) -> str:
    name, number = f"{stem}{suffix}", 2
    while (folder / name).exists() or (folder / (name + PARTIAL)).exists():
        name, number = f"{stem}-{number}{suffix}", number + 1
    return name
