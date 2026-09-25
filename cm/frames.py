"""Reading a video piece's frames file, `frames.md`: what is said and shown, frame by frame.

The file is written by hand, so it is read strictly and every problem is reported at once,
each naming the frame and line, rather than guessing what was meant. A frames file looks
like this:

    # Title of the short

    Format: vertical
    Captions: on

    ## Hook (4s)
    Script: What is said while this frame is on screen.
    On screen: The words and pictures shown.
    Animation: How they move.

- Above the first frame, `Format:` and `Captions:` are settings; anything else there is a
  note and is ignored.
- Each `## ` heading starts a frame. A length in brackets at its end, like `(4s)`, fixes
  how long the frame runs; without one, the length comes from how much is said.
- Inside a frame, a line that does not start with `Script:`, `On screen:` or `Animation:`
  carries on the field above it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .formats import DEFAULT, FORMATS, Format

TEMPLATE = Path(__file__).resolve().parent / "starter" / "piece" / "frames.md"

SETTING = re.compile(r"^(format|captions)\s*:\s*(.*)$", re.IGNORECASE)
FIELD = re.compile(r"^(script|on screen|animation)\s*:\s*(.*)$", re.IGNORECASE)
LENGTH = re.compile(r"\((\d+(?:\.\d+)?)\s*s\)\s*$")
CAPTIONS = {"on": True, "off": False}


@dataclass(frozen=True)
class Frame:
    title: str
    seconds: float | None        # None: worked out from the script
    script: str
    on_screen: str
    animation: str


@dataclass(frozen=True)
class Frames:
    title: str
    format: Format
    captions: bool
    frames: tuple[Frame, ...]

    def summary(self) -> str:
        count = len(self.frames)
        return (f"{count} frame{'' if count == 1 else 's'} · {self.format.name} "
                f"{self.format.width}×{self.format.height} · captions {'on' if self.captions else 'off'}")


class FramesError(ValueError):
    """The file cannot be read as frames. `problems` lists each one, in file order."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def template() -> str:
    """What a new video piece's frames file starts from."""
    return TEMPLATE.read_text(encoding="utf-8")


def parse(text: str) -> Frames:
    problems: list[str] = []
    title = ""
    settings: dict[str, str] = {}
    frames: list[dict] = []
    field: str | None = None       # the field that a plain line carries on

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            frames.append(_new_frame(line[3:].strip(), number, problems))
            field = None
            continue
        if not frames:
            if line.startswith("# ") and not title:
                title = line[2:].strip()
            elif match := SETTING.match(line):
                key = match.group(1).lower()
                if key in settings:
                    problems.append(f"Line {number}: {match.group(1)} is set twice.")
                settings[key] = match.group(2).strip()
            continue                                     # anything else up here is a note
        frame = frames[-1]
        if match := FIELD.match(line):
            field = match.group(1).lower()
            if frame[field] is not None:
                problems.append(f"{frame['name']}, line {number}: {match.group(1)} appears twice.")
            frame[field] = match.group(2).strip()
        elif field:
            frame[field] = f"{frame[field]}\n{line}".strip()
        else:
            problems.append(f"{frame['name']}, line {number}: text before Script, On screen or "
                            "Animation. Start the line with one of those.")

    fmt = _format(settings.get("format"), problems)
    captions = _captions(settings.get("captions"), problems)
    if not frames:
        problems.append("No frames yet. Each frame starts with a heading: ## Title")
    for frame in frames:
        if not frame["script"] and frame["seconds"] is None:
            problems.append(f"{frame['name']} has no script, so give it a length, like (3s), "
                            "at the end of its heading.")
    if problems:
        raise FramesError(problems)

    return Frames(title=title, format=fmt, captions=captions, frames=tuple(
        Frame(title=f["title"], seconds=f["seconds"], script=f["script"] or "",
              on_screen=f["on screen"] or "", animation=f["animation"] or "")
        for f in frames))


def _new_frame(heading: str, number: int, problems: list[str]) -> dict:
    seconds = None
    if match := LENGTH.search(heading):
        seconds = float(match.group(1))
        heading = heading[:match.start()].strip()
    if not heading:
        name = f"The frame on line {number}"
    elif heading.lower().startswith("frame"):
        name = heading                          # "Frame 3 — the path" names itself
    else:
        name = f"Frame “{heading}”"
    if seconds == 0:
        problems.append(f"{name} is 0 seconds long. Give it a length above zero, or none.")
    return {"title": heading, "name": name, "seconds": seconds,
            "script": None, "on screen": None, "animation": None}


def _format(value: str | None, problems: list[str]) -> Format:
    if value is None:
        return DEFAULT
    if value.lower() not in FORMATS:
        problems.append(f"Format: “{value}” is not one of {', '.join(FORMATS)}.")
        return DEFAULT
    return FORMATS[value.lower()]


def _captions(value: str | None, problems: list[str]) -> bool:
    if value is None:
        return True
    if value.lower() not in CAPTIONS:
        problems.append(f"Captions: “{value}” should be on or off.")
        return True
    return CAPTIONS[value.lower()]
