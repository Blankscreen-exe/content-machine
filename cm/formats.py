"""The shapes a video can be rendered in, named so a frames file can ask for one.

Adding a shape is one line here; everything that draws a video reads its size from this.
"""
from __future__ import annotations

from dataclasses import dataclass

# Every video renders at this many frames a second.
FPS = 30


@dataclass(frozen=True)
class Format:
    name: str
    width: int
    height: int


FORMATS = {f.name: f for f in (
    Format("vertical", 1080, 1920),      # YouTube Shorts, Reels, TikTok
    Format("square", 1080, 1080),
    Format("portrait", 1080, 1350),      # the tallest a feed post shows uncropped
    Format("landscape", 1920, 1080),
)}
DEFAULT = FORMATS["vertical"]
