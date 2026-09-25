"""The video toolchain: Node, the npm packages that render video, and the browser they draw in.

`cm video setup` installs it into the workspace, and is the only step that downloads
anything for video. What it guards against is a tampered package, so each step is
checked rather than trusted:

- `npm ci` installs exactly what `package-lock.json` lists, and refuses any package whose
  contents do not match the checksum recorded there. The lockfile's versions were all at
  least two weeks old when it was made, so a release hijacked and pulled within days
  never gets in.
- No package runs code while it installs (`--ignore-scripts`, also set in `.npmrc`).
- `npm audit signatures` checks every package was signed by the npm registry.
- Remotion's headless Chrome comes from Google's Chrome for Testing downloads.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

MIN_NODE = 18
# What the workspace must hold before anything is installed; `cm init` puts them there.
MANIFESTS = ("package.json", "package-lock.json")


class ToolchainError(RuntimeError):
    """A step could not be done; the message says what to do about it."""


def setup(workspace: Path, say: Callable[[str], None] = print) -> None:
    """Install and check the toolchain in `workspace`, saying what each step does."""
    missing = [name for name in MANIFESTS if not (workspace / name).is_file()]
    if missing:
        raise ToolchainError(f"{', '.join(missing)} not found in {workspace}. Run `cm init` first.")
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
