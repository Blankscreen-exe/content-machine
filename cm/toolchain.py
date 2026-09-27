"""The video toolchain: Node, the npm packages that render video, and the browser they draw in.

`cm video setup` installs it into the workspace, and is the only step that downloads
anything for video. It first puts the app's pinned package list in the workspace
(package.json, package-lock.json, .npmrc from cm/starter/video/): those files are the app's,
not yours, so an update to them reaches the workspace the next time setup runs. What it guards against is a tampered package, so each step is
checked rather than trusted:

- `npm ci` installs exactly what `package-lock.json` lists, and refuses any package whose
  contents do not match the checksum recorded there. The lockfile's versions were all at
  least two weeks old when it was made, so a release hijacked and pulled within days
  never gets in.
- No package runs code while it installs (`--ignore-scripts`, also set in `.npmrc`).
- `npm audit signatures` checks every package was signed by the npm registry.
- Remotion's headless Chrome comes from Google's Chrome for Testing downloads.
- whisper.cpp and its speech model, which time captions to the voice, are checked against
  SHA-256 checksums recorded in whisper.py before they are kept.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from . import whisper

MIN_NODE = 18
# Windows cannot start a program whose path is longer than 260 characters, and Remotion keeps
# its browser about 120 characters deep inside the workspace. Past this, rendering fails.
MAX_WORKSPACE_PATH = 130
# The app's pinned package list, put in the workspace root, where every piece folder finds it.
STARTER = Path(__file__).resolve().parent / "starter" / "video"
MANIFESTS = ("package.json", "package-lock.json", ".npmrc")


class ToolchainError(RuntimeError):
    """A step could not be done; the message says what to do about it."""


def setup(workspace: Path, say: Callable[[str], None] = print) -> None:
    """Install and check the toolchain in `workspace`, saying what each step does."""
    if sys.platform == "win32" and len(str(workspace)) > MAX_WORKSPACE_PATH:
        raise ToolchainError(f"The workspace path is {len(str(workspace))} characters long. Windows cannot start "
                             f"programs from paths over 260 characters, and the video toolchain keeps its browser "
                             f"deep inside the workspace. Use a workspace path of at most {MAX_WORKSPACE_PATH} "
                             "characters (set CM_WORKSPACE, or move the repository).")
    workspace.mkdir(parents=True, exist_ok=True)
    for name in MANIFESTS:
        source, target = STARTER / name, workspace / name
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            shutil.copyfile(source, target)
            say(f"Put the app's pinned {name} in the workspace.")
    say(f"Node {'.'.join(map(str, node_version()))} found.")
    npm = _tool("npm", "npm comes with Node: https://nodejs.org")

    say("Installing the packages in package-lock.json, each checked against its checksum...")
    _run([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"], workspace,
         "Installing the packages failed. The output above says why.")
    say("Checking every package was signed by the npm registry...")
    _run([npm, "audit", "signatures"], workspace,
         "A package failed its signature check, so it may have been tampered with. "
         "Do not render with it; delete node_modules and report the package named above.")
    say("Fetching the browser that draws each frame (once, from Google's Chrome for Testing)...")
    _run([npm, "exec", "--no", "--", "remotion", "browser", "ensure"], workspace,
         "Fetching the browser failed. Check the connection and run `cm video setup` again.")
    try:
        whisper.install(workspace, say=say)
    except whisper.WhisperError as exc:
        raise ToolchainError(str(exc)) from exc
    say("The video toolchain is ready.")


def node_version() -> tuple[int, ...]:
    """The installed Node's version, or an error saying which is needed."""
    node = _tool("node", f"Install Node {MIN_NODE} or later: https://nodejs.org")
    output = subprocess.run([node, "--version"], capture_output=True, text=True, check=False).stdout
    match = re.match(r"v(\d+)\.(\d+)\.(\d+)", output.strip())
    if not match:
        raise ToolchainError(f"Could not read Node's version from {output.strip()!r}.")
    version = tuple(int(part) for part in match.groups())
    if version[0] < MIN_NODE:
        raise ToolchainError(f"Node {output.strip()} is too old; install Node {MIN_NODE} or later.")
    return version


def _tool(name: str, how_to_get_it: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ToolchainError(f"{name} is not on PATH. {how_to_get_it}")
    return path


def _run(argv: list[str], cwd: Path, failure: str) -> None:
    """Run a step with its output shown as it goes, since installs take a while."""
    if subprocess.run(argv, cwd=cwd, check=False).returncode != 0:
        raise ToolchainError(failure)
