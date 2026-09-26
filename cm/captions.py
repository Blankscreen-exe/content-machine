"""Captions timed to the voice: the script's own words, each at the moment it is said.

whisper.py hears the take. Its words are matched to the script's in order (difflib), so a
word misheard or added in the reading does not shift the rest; a script word it did not
hear is given a time between its neighbours. The captions then show the script as written,
at the pace of the voice. What whisper heard is kept beside the take, `take-4.words.json`
beside `take-4.webm`, so each take is heard once.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from .timing import WORDS_PER_SECOND
from .whisper import MODEL, Heard

# A script word with no heard neighbour on one side is placed this far from the other.
GAP = 1 / WORDS_PER_SECOND


def heard_path(take: Path) -> Path:
    return take.with_name(f"{take.stem}.words.json")


def load(take: Path) -> list[Heard] | None:
    """What was heard in `take`, if it has been heard with the model in use."""
    path = heard_path(take)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("model") != MODEL:
        return None
    return [Heard(text, at) for text, at in data["words"]]


def save(take: Path, heard: list[Heard]) -> None:
    heard_path(take).write_text(
        json.dumps({"model": MODEL, "words": [[h.text, h.at] for h in heard]}, indent=0), encoding="utf-8")


def _plain(word: str) -> str:
    """A word as compared: lower case, letters and digits only, so "AI-generated," matches
    "AI-generated" and "ai generated" does not throw the rest out of step."""
    return re.sub(r"[\W_]+", "", word.lower())


def when_said(script: list[str], heard: list[Heard]) -> list[float] | None:
    """For each script word, the time in the take it is said; None if none of it was heard."""
    wanted = [i for i, word in enumerate(script) if _plain(word)]     # words, not stray dashes
    times: list[float | None] = [None] * len(script)
    matcher = SequenceMatcher(None, [_plain(script[i]) for i in wanted], [_plain(h.text) for h in heard],
                              autojunk=False)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            times[wanted[block.a + k]] = heard[block.b + k].at
    known = [i for i, t in enumerate(times) if t is not None]
    if not known:
        return None
    for i, t in enumerate(times):
        if t is not None:
            continue
        before = max((k for k in known if k < i), default=None)
        after = min((k for k in known if k > i), default=None)
        if before is not None and after is not None:          # between two heard words
            times[i] = times[before] + (times[after] - times[before]) * (i - before) / (after - before)
        elif after is not None:                                # before anything heard
            times[i] = max(0.0, times[after] - (after - i) * GAP)
        else:                                                  # after the last word heard
            times[i] = times[before] + (i - before) * GAP
    # never earlier than the word before it, whatever the matching made of a repeat
    for i in range(1, len(times)):
        times[i] = max(times[i], times[i - 1])
    return times


def timed_scenes(scenes: list[dict], heard: list[Heard], voice: dict, fps: int) -> list[list[dict] | None]:
    """Each scene's script words with the frames they are said at, from the scene's start:
    [{"text", "from", "to"}], where "to" is when the next word starts. None for a scene
    with no script, or for every scene if none of the take was heard.

    A word keeps the moment it is said even when that falls outside its scene, as the last
    word of a line often does: captions follow the voice, not the cuts between pictures.

    `voice` is the voice as the render is handed it (voice.props): a take at `trimBefore`
    frames plays at video frame `from`."""
    per_scene = [scene["script"].split() for scene in scenes]
    times = when_said([word for words in per_scene for word in words], heard)
    if times is None:
        return [None] * len(scenes)
    frames = [voice["from"] + round(t * fps) - voice["trimBefore"] for t in times]
    placed: list[list[dict] | None] = []
    for scene, words in zip(scenes, per_scene):
        mine, frames = frames[:len(words)], frames[len(words):]
        if not words:
            placed.append(None)
            continue
        starts = [f - scene["from"] for f in mine]
        ends = starts[1:] + [max(scene["duration"], starts[-1] + 1)]
        placed.append([{"text": word, "from": start, "to": end}
                       for word, start, end in zip(words, starts, ends)])
    return placed
