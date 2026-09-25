"""What a brand reuses across its pieces: music, images such as a portrait or a logo, and
its video kit.

They live in `resources/<brand slug>/` in the workspace, a folder per kind, so a video of
any piece can pick from them. Uploads follow a piece's asset rules (assets.py): only the
listed types, written whole or not at all, named by the app. The kind is decided by the
file's type, so a song can never land among the images. The kit is code, written in a
session rather than uploaded, so it has a folder here but no upload.
"""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from . import assets
from .settings import get_settings

# What can be uploaded, by the folder it goes in.
KINDS = {
    "images": assets.IMAGE_LIMITS,
    "music": assets.AUDIO_LIMITS,
}
KIT = "kit"


class UnknownKind(ValueError):
    """Asked for a kind of resource that does not exist."""


def brand_folder(slug: str) -> Path:
    return get_settings().resources_dir / slug


def folder(slug: str, kind: str) -> Path:
    if kind not in KINDS:
        raise UnknownKind(f"{kind!r} is not a kind of resource ({', '.join(KINDS)})")
    return brand_folder(slug) / kind


def kit_folder(slug: str) -> Path:
    return brand_folder(slug) / KIT


def listing(slug: str) -> dict[str, list[assets.Asset]]:
    return {kind: assets.listing(folder(slug, kind)) for kind in KINDS}


def save(slug: str, filename: str, source: BinaryIO) -> tuple[str, str]:
    """Store one upload in the folder its type belongs to. Returns (kind, stored name)."""
    suffix = Path(filename or "").suffix.lower()
    for kind, limits in KINDS.items():
        if suffix in limits:
            return kind, assets.save(folder(slug, kind), filename, source, limits=limits)
    accepted = "; ".join(f"{kind}: {', '.join(sorted(limits))}" for kind, limits in KINDS.items())
    raise assets.BadAsset(f"{filename or 'That file'}: {suffix or 'files without an extension'} "
                          f"is not a brand resource ({accepted})")


def path_of(slug: str, kind: str, name: str) -> Path:
    path = assets.path_of(folder(slug, kind), name)
    if path.suffix.lower() not in KINDS[kind]:       # an image cannot be fetched as music
        raise FileNotFoundError(f"{name!r} is not in {kind}")
    return path


def trash(slug: str, kind: str, name: str) -> Path:
    """Move one resource to `trash/<brand>/resources/<kind>/`, and say where."""
    return assets.move(path_of(slug, kind, name), get_settings().trash_dir / slug / "resources" / kind)
