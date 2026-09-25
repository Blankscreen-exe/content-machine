"""A video piece's voice: the takes recorded for it, and how the chosen one is mixed in.

Takes live in the piece's `voice/` folder, named by the app (`take-1.webm`, `take-2.webm`)
as they arrive. A take is never cut: trimming and lining up are numbers in `voice/mix.json`,
along with the music chosen from the brand's library, so any choice can be undone.

    {"take": "take-2.webm", "offset": 0.2, "trim_start": 0.0, "trim_end": null,
     "volume": 1.0, "music": "calm-pad.wav", "music_volume": 0.12}

`offset` is where the take starts against the video, in seconds: later if positive; if
negative, that much of the take's start is skipped. `trim_start` and `trim_end` are points
in the take itself. A mix.json that cannot be read is reported, never replaced, since it
holds choices made by ear.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import BinaryIO

from . import assets

FOLDER = "voice"
MIX_FILE = "mix.json"
TAKE_STEM = "take"
# A browser records WebM (or M4A in Safari); a take edited elsewhere may come back as WAV or MP3.
TAKE_LIMITS = {".webm": 200 * assets.MB, **assets.AUDIO_LIMITS}
# Beyond these a setting is surely a slip of the keyboard, not a choice.
MAX_OFFSET = 60.0
MAX_VOLUME = 2.0


class MixError(ValueError):
    """mix.json, or a change to it, does not make sense; the message says what and where."""


@dataclass(frozen=True)
class Mix:
    take: str | None = None
    offset: float = 0.0
    trim_start: float = 0.0
    trim_end: float | None = None
    volume: float = 1.0
    music: str | None = None
    music_volume: float = 0.12


def folder_of(piece_folder: Path) -> Path:
    return piece_folder / FOLDER


def takes(piece_folder: Path) -> list[assets.Asset]:
    return [take for take in assets.listing(folder_of(piece_folder))
            if Path(take.name).suffix.lower() in TAKE_LIMITS]


def save_take(piece_folder: Path, filename: str, source: BinaryIO) -> str:
    """Store a new take, numbered after the others, and make it the one used."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in TAKE_LIMITS:
        raise assets.BadAsset(f"{filename or 'That file'}: a take is one of {', '.join(sorted(TAKE_LIMITS))}")
    number = 1 + max((_take_number(take.name) for take in takes(piece_folder)), default=0)
    name = assets.save(folder_of(piece_folder), f"{TAKE_STEM}-{number}{suffix}", source, limits=TAKE_LIMITS)
    mix = read_mix(piece_folder)
    write_mix(piece_folder, Mix(**{**asdict(mix), "take": name, "offset": 0.0, "trim_start": 0.0, "trim_end": None}))
    return name


def _take_number(name: str) -> int:
    """3 for take-3.webm; 0 for a file named some other way."""
    stem = Path(name).stem
    number = stem.removeprefix(f"{TAKE_STEM}-")
    return int(number) if number != stem and number.isdigit() else 0


def take_path(piece_folder: Path, name: str) -> Path:
    path = assets.path_of(folder_of(piece_folder), name)
    if path.suffix.lower() not in TAKE_LIMITS:
        raise FileNotFoundError(f"{name!r} is not a take")
    return path


def trash_take(piece_folder: Path, name: str, trash_dir: Path) -> Path:
    """Move a take to `trash_dir`. If it was the one used, the mix no longer uses one."""
    moved = assets.move(take_path(piece_folder, name), trash_dir)
    mix = read_mix(piece_folder)
    if mix.take == name:
        write_mix(piece_folder, Mix(**{**asdict(mix), "take": None}))
    return moved


def read_mix(piece_folder: Path) -> Mix:
    path = folder_of(piece_folder) / MIX_FILE
    if not path.is_file():
        return Mix()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MixError(f"{path} cannot be read ({exc}). Fix or delete it; it is not replaced "
                       "automatically, since it holds choices made by ear.") from exc
    if not isinstance(data, dict):
        raise MixError(f"{path} should hold one object of settings.")
    known = {f.name for f in fields(Mix)}
    if unknown := set(data) - known:
        raise MixError(f"{path} has settings this app does not know: {', '.join(sorted(unknown))}.")
    return check(Mix(**data), where=str(path))


def write_mix(piece_folder: Path, mix: Mix) -> None:
    """Save the mix whole or not at all: written beside it, then moved into place."""
    mix = check(mix)
    folder = folder_of(piece_folder)
    folder.mkdir(parents=True, exist_ok=True)
    partial = folder / f"{MIX_FILE}{assets.PARTIAL}"
    partial.write_text(json.dumps(asdict(mix), indent=1), encoding="utf-8")
    os.replace(partial, folder / MIX_FILE)


def check(mix: Mix, where: str = "The mix") -> Mix:
    """The mix as numbers that make sense, or an error naming the one that does not."""
    def number(name: str, low: float, high: float) -> None:
        value = getattr(mix, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            raise MixError(f"{where}: {name} should be a number from {low:g} to {high:g}, not {value!r}.")

    for name in ("take", "music"):
        if getattr(mix, name) is not None and not isinstance(getattr(mix, name), str):
            raise MixError(f"{where}: {name} should be a file name or nothing.")
    number("offset", -MAX_OFFSET, MAX_OFFSET)
    number("trim_start", 0.0, float("inf"))
    number("volume", 0.0, MAX_VOLUME)
    number("music_volume", 0.0, MAX_VOLUME)
    if mix.trim_end is not None:
        number("trim_end", 0.0, float("inf"))
        if mix.trim_end <= mix.trim_start:
            raise MixError(f"{where}: trim_end ({mix.trim_end:g}s) should come after trim_start ({mix.trim_start:g}s).")
        if mix.trim_end <= mix.trim_start + max(0.0, -mix.offset):
            raise MixError(f"{where}: with an offset of {mix.offset:g}s, none of the take before "
                           f"trim_end ({mix.trim_end:g}s) is heard.")
    return mix


def props(mix: Mix, fps: int) -> dict:
    """The voice and music as a render is handed them, in frames. The files themselves are
    put beside the render as `voice<suffix>` and `music<suffix>`; see renders.py."""
    voice = None
    if mix.take:
        offset = round(mix.offset * fps)
        voice = {
            "src": public_name("voice", mix.take),
            "from": max(0, offset),
            # a negative offset skips that much more of the take's start
            "trimBefore": round(mix.trim_start * fps) + max(0, -offset),
            "trimAfter": round(mix.trim_end * fps) if mix.trim_end is not None else None,
            "volume": mix.volume,
        }
    music = {"src": public_name("music", mix.music), "volume": mix.music_volume} if mix.music else None
    return {"voice": voice, "music": music}


def public_name(role: str, name: str) -> str:
    """What a file is called beside the render: its role, keeping its type."""
    return f"{role}{Path(name).suffix.lower()}"
