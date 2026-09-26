"""Speech-to-text on this machine, with whisper.cpp: when each word of a take is said.

Only captions need it, and only for the time of each word: the words shown are the
script's (captions.py). So a small English model is enough, and nothing leaves the machine.

`install` fetches a pinned whisper.cpp release and model into the workspace's `.cm/whisper/`
and checks each against the SHA-256 recorded here before keeping it, so a file changed at
its source is refused rather than run. Only the Windows build is fetched: it is the one
whisper.cpp publishes ready to run and the one this has been tested with. Swapping
whisper.cpp for another recogniser means changing this module.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

VERSION = "1.9.2"
RELEASE = (f"https://github.com/ggml-org/whisper.cpp/releases/download/v{VERSION}/whisper-bin-x64.zip",
           "49dcc16de826f20bd53d44f947a1ae49dfa81f86cad67a64d80820cb192d674a")
MODEL = "base.en"
# A fixed revision of the model repository, so the file behind the address cannot change.
MODEL_FILE = (f"https://huggingface.co/ggerganov/whisper.cpp/resolve/"
              f"5359861c739e955e79d9a303bcbc70fb988958b1/ggml-{MODEL}.bin",
              "a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002")
CHUNK = 1024 * 1024


class WhisperError(RuntimeError):
    """whisper.cpp could not be installed or run; the message says what to do."""


@dataclass(frozen=True)
class Heard:
    """A word as whisper heard it, and when in the take it is said, in seconds."""

    text: str
    at: float


def folder(workspace: Path) -> Path:
    return workspace / ".cm" / "whisper"


def _program(workspace: Path) -> Path:
    return folder(workspace) / f"whisper-{VERSION}" / "Release" / "whisper-cli.exe"


def _model(workspace: Path) -> Path:
    return folder(workspace) / f"ggml-{MODEL}.bin"


def installed(workspace: Path) -> bool:
    return _program(workspace).is_file() and _model(workspace).is_file()


def install(workspace: Path, say: Callable[[str], None] = print) -> None:
    """Fetch and check the pinned release and model, unless they are already in place."""
    if sys.platform != "win32":
        raise WhisperError("Captions timed to the voice use whisper.cpp's Windows build, the only one "
                           "set up here. On another system, captions are spread over each frame instead.")
    if installed(workspace):
        say(f"whisper.cpp {VERSION} and the {MODEL} model are already in place.")
        return
    target = folder(workspace)
    target.mkdir(parents=True, exist_ok=True)
    if not _program(workspace).is_file():
        say(f"Fetching whisper.cpp {VERSION}, which times captions to the voice...")
        archive = _download(*RELEASE, target / "whisper-bin-x64.zip")
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(target / f"whisper-{VERSION}")
        archive.unlink()
    if not _model(workspace).is_file():
        say(f"Fetching the {MODEL} speech model (about 150 MB, once)...")
        _download(*MODEL_FILE, _model(workspace))


def _download(url: str, sha256: str, target: Path) -> Path:
    """Fetch `url` to `target`, keeping it only if its SHA-256 is the one expected."""
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as out:
            while chunk := response.read(CHUNK):
                digest.update(chunk)
                out.write(chunk)
    except OSError as exc:
        partial.unlink(missing_ok=True)
        raise WhisperError(f"Could not fetch {url} ({exc}). Check the connection and run "
                           "`cm video setup` again.") from exc
    if digest.hexdigest() != sha256:
        partial.unlink(missing_ok=True)
        raise WhisperError(f"{url} did not match its recorded checksum, so it may have been changed "
                           "at its source. It was not kept. Do not install it by hand; report it.")
    partial.replace(target)
    return target


def transcribe(workspace: Path, wav: Path) -> list[Heard]:
    """The words in `wav`, a 16 kHz mono WAV, each with when it is said."""
    if not installed(workspace):
        raise WhisperError("whisper.cpp is not installed. Run `cm video setup`.")
    out = wav.with_suffix("")
    argv = [str(_program(workspace)), "-m", str(_model(workspace)), "-f", str(wav), "-l", "en",
            # the full JSON, with a time for each token worked out by DTW, which needs
            # flash attention off to give one
            "-ojf", "-dtw", MODEL, "-nfa", "-np", "-of", str(out)]
    run = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    result = out.with_suffix(".json")
    if run.returncode != 0 or not result.is_file():
        raise WhisperError("whisper.cpp could not read the take:\n" + (run.stderr.strip()[-2000:] or "no output"))
    return words(json.loads(result.read_text(encoding="utf-8")))


def words(result: dict) -> list[Heard]:
    """Whisper's tokens joined back into words. A token starting with a space starts a word;
    the rest (the second half of a long word, a hyphen, punctuation) belong to the one before.
    A word is said when its first token is."""
    heard: list[Heard] = []
    for segment in result.get("transcription", []):
        for token in segment.get("tokens", []):
            text = token.get("text", "")
            if not text.strip() or text.startswith("[") or text.startswith("<|"):
                continue                          # markers such as [_BEG_], not speech
            at = token.get("t_dtw", -1)
            at = at / 100 if at >= 0 else token["offsets"]["from"] / 1000
            if text.startswith(" ") or not heard:
                heard.append(Heard(text.strip(), at))
            else:
                heard[-1] = Heard(heard[-1].text + text, heard[-1].at)
    return heard

