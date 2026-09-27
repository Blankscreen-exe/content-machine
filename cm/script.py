"""What is said in a video, written out beside it: `script.md` to read from, and
`assets/captions.srt`, subtitles to upload.

Both are written with every render, from the timings the video was drawn to, so a voice
recorded somewhere else (in YouTube's Shorts editor, say) can keep pace with the pictures,
and captions can be added there instead of drawn into the video. When captions are timed to
a take, the subtitles follow that take's voice.
"""
from __future__ import annotations

from pathlib import Path

SCRIPT_FILE = "script.md"          # beside frames.md; generated, so read-only in the editor
CAPTIONS_FILE = "captions.srt"     # in the piece's assets, to download
# About as much as a subtitle line shows comfortably on a phone.
CUE_CHARS = 42


def clock(frame: int, fps: int) -> str:
    """0:07.2"""
    seconds = frame / fps
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def _srt_time(frame: int, fps: int) -> str:
    """00:00:07,200"""
    ms = round(frame * 1000 / fps)
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _chunks(words: list[str]) -> list[list[int]]:
    """The positions of `words`, grouped into lines of at most CUE_CHARS characters."""
    lines: list[list[int]] = [[]]
    used = 0
    for i, word in enumerate(words):
        if lines[-1] and used + 1 + len(word) > CUE_CHARS:
            lines.append([])
            used = 0
        used += (1 if lines[-1] else 0) + len(word)
        lines[-1].append(i)
    return [line for line in lines if line]


def cues(props: dict) -> list[tuple[int, int, str]]:
    """(first frame, last frame, text) for each subtitle, in order. Each scene's words are
    shown over the time they are said: from the take when captions are timed to one,
    otherwise spread over the scene's estimated speech."""
    found: list[tuple[int, int, str]] = []
    for scene in props["scenes"]:
        words = scene["script"].split()
        if not words:
            continue
        timed = scene.get("words")
        if timed:
            starts = [scene["from"] + word["from"] for word in timed]
            ends = [scene["from"] + word["to"] for word in timed]
        else:
            speech = max(scene["speech"], 1)
            starts = [scene["from"] + speech * i // len(words) for i in range(len(words))]
            ends = starts[1:] + [scene["from"] + speech]
        for line in _chunks(words):
            found.append((starts[line[0]], max(ends[line[-1]], starts[line[0]] + 1),
                           " ".join(words[i] for i in line)))
    return found


def srt(props: dict) -> str:
    fps = props["fps"]
    return "\n".join(f"{n}\n{_srt_time(start, fps)} --> {_srt_time(end, fps)}\n{text}\n"
                     for n, (start, end, text) in enumerate(cues(props), start=1))


def script(props: dict, title: str) -> str:
    fps = props["fps"]
    spoken = [scene for scene in props["scenes"] if scene["script"].strip()]
    lines = [f"# Script: {title}", "",
             "Written with every render from frames.md, to the timings the video was drawn to. "
             "Change frames.md and render again, rather than editing this.", "",
             f"{props['total'] / fps:.1f} seconds · {props['width']}×{props['height']} · "
             f"{len(props['scenes'])} frames, {len(spoken)} with words"]
    for scene in props["scenes"]:
        lines += ["", f"## {clock(scene['from'], fps)} · {scene['title'] or 'Untitled frame'}", ""]
        if scene["script"].strip():
            lines.append(" ".join(scene["script"].split()))
            lines += ["", f"_Said by {clock(scene['from'] + scene['speech'], fps)}; "
                          f"the frame runs to {clock(scene['from'] + scene['duration'], fps)}._"]
        else:
            lines.append(f"_Nothing said; the frame runs to {clock(scene['from'] + scene['duration'], fps)}._")
    return "\n".join(lines) + "\n"


def write(props: dict, title: str, piece_folder: Path, assets_dir: Path) -> tuple[Path, Path]:
    """Write both files for a render, replacing the last render's. Returns their paths."""
    script_path = piece_folder / SCRIPT_FILE
    script_path.write_text(script(props, title), encoding="utf-8")
    assets_dir.mkdir(parents=True, exist_ok=True)
    captions_path = assets_dir / CAPTIONS_FILE
    captions_path.write_text(srt(props), encoding="utf-8")
    return script_path, captions_path
