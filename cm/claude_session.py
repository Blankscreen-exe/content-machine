"""How a Claude session is started: what it may touch, and the tools it reaches the app with.

A session runs in Claude Code's restricted mode. That takes away Bash, PowerShell and every
other way to run code, so the database can only be reached through the content machine
tools (mcp_server.py), which have no way to publish, delete or move a piece past wip. The
file tools work only in the session's folder and the ones listed here: the brand's own
content and resources, and the example kit to copy from. Another brand's folders, the
database and the app's state are all outside. Restricted mode also ignores the settings
files a session could edit to loosen any of this.

The config Claude Code starts the tools from is written to `.cm/sessions/`, which never
leaves this machine: it names this machine's Python and workspace.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from . import resources
from .settings import get_settings
from .terminals import TerminalError

# Claude Code names each tool mcp__<server>__<tool>; allowing mcp__<server> allows them all,
# so a session filing twenty pieces does not stop to ask twenty times.
SERVER_NAME = "cm"


def command(brand_slug: str, prompt: str) -> list[str]:
    """The command that starts a session for `brand_slug`. Fails loudly if Claude Code is not
    installed."""
    executable = shutil.which("claude")
    if not executable:
        raise TerminalError("Claude Code is not on PATH. Install it, or open the folder yourself.")
    return [executable,
            "--restricted",
            "--strict-mcp-config",                 # these tools only, not any configured elsewhere
            "--mcp-config", str(write_config(brand_slug)),
            "--allowedTools", f"mcp__{SERVER_NAME}",
            "--add-dir", *(str(folder) for folder in folders(brand_slug)),
            "--",                                  # the options above take several values: end them
            prompt]


def folders(brand_slug: str) -> list[Path]:
    """Where a session may read and write besides its own folder. Made if missing, as
    Claude Code refuses a folder that does not exist."""
    settings = get_settings()
    brand_folders = [settings.content_dir / brand_slug, resources.brand_folder(brand_slug)]
    for folder in brand_folders:
        folder.mkdir(parents=True, exist_ok=True)
    example_kit = settings.workspace / "video" / "example-kit"
    return brand_folders + ([example_kit] if example_kit.is_dir() else [])


def write_config(brand_slug: str) -> Path:
    """The MCP config that starts the tools for `brand_slug`, with the Python running this app
    and its workspace, so the tools open the same database whatever folder they start in."""
    settings = get_settings()
    path = settings.state_dir / "sessions" / f"{brand_slug}.mcp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    config = {"mcpServers": {SERVER_NAME: {
        "type": "stdio",
        "command": sys.executable,
        "args": ["-m", "cm.cli", "mcp", "--brand", brand_slug],
        "env": {"CM_WORKSPACE": str(settings.workspace)},
    }}}
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path
