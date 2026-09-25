"""How long each frame of a video runs, worked out from its frames file.

A frame with a length in its heading runs exactly that long. Otherwise it runs as long as
its script takes to say at an ordinary speaking pace, plus a breath before the next frame.
The voice is recorded afterwards, reading along to these timings, so they set the pace.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .formats import FPS, Format
from .frames import Frame, Frames

# About 150 words a minute: an unhurried pace for a script read to camera.
WORDS_PER_SECOND = 2.5
# A breath after each frame's script, before the next begins.
PAUSE_SECONDS = 0.4
# Long enough to read a word or two, for a frame with almost nothing said.
MIN_SECONDS = 1.5


@dataclass(frozen=True)
class Scene:
    """One frame of the frames file, placed on the video's timeline. Lengths are in frames."""

    frame: Frame
    start: int
    length: int
    speech: int         # how long its script takes to say, from its start


@dataclass(frozen=True)
class Timeline:
    format: Format
    captions: bool
    scenes: tuple[Scene, ...]
    fps: int = FPS

    @property
    def total(self) -> int:
        return sum(scene.length for scene in self.scenes)

    @property
    def seconds(self) -> float:
        return self.total / self.fps


def speaking_seconds(script: str) -> float:
    return len(script.split()) / WORDS_PER_SECOND


def timeline(frames: Frames, fps: int = FPS) -> Timeline:
    scenes, start = [], 0
    for frame in frames.frames:
        said = speaking_seconds(frame.script)
        seconds = frame.seconds if frame.seconds is not None else max(MIN_SECONDS, said + PAUSE_SECONDS)
        length = max(1, round(seconds * fps))
        speech = min(length, math.ceil(said * fps))
        scenes.append(Scene(frame=frame, start=start, length=length, speech=speech))
        start += length
    return Timeline(format=frames.format, captions=frames.captions, scenes=tuple(scenes), fps=fps)


def props(line: Timeline) -> dict:
    """What the video is handed when it renders; the shape `VideoProps` in remotion/props.ts."""
    return {
        "fps": line.fps,
        "width": line.format.width,
        "height": line.format.height,
        "total": line.total,
        "captions": line.captions,
        "scenes": [{
            "title": scene.frame.title,
            "from": scene.start,
            "duration": scene.length,
            "speech": scene.speech,
            "script": scene.frame.script,
            "onScreen": scene.frame.on_screen,
            "animation": scene.frame.animation,
        } for scene in line.scenes],
    }
