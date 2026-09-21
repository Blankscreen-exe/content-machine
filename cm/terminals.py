"""Opening a terminal in a piece's folder.

Each terminal gets a recipe: how to set the working folder, how to set the window or tab
title, and where the command goes. Supporting another one means adding an entry here.

Arguments are passed as a list and never through a shell, so titles and prompts with
spaces need no quoting.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Terminal:
    key: str
    label: str
    executable: str
    platforms: tuple[str, ...]
    # {title}, {cwd} and {command} are replaced; {command} expands to the full command list
    template: list[str] = field(default_factory=list)
    # Some terminals set the working directory themselves; others need it on the process.
    sets_own_cwd: bool = True

    def available(self) -> str | None:
        if sys.platform not in self.platforms:
            return None
        return shutil.which(self.executable)


TERMINALS: tuple[Terminal, ...] = (
    Terminal("wt", "Windows Terminal", "wt.exe", ("win32",),
             ["new-tab", "--title", "{title}", "--startingDirectory", "{cwd}", "{command}"]),
    Terminal("powershell", "PowerShell", "powershell.exe", ("win32",),
             ["-NoExit", "-Command", "{command}"], sets_own_cwd=False),
    Terminal("cmd", "Command Prompt", "cmd.exe", ("win32",),
             ["/k", "title", "{title}", "&", "{command}"], sets_own_cwd=False),
    Terminal("gnome-terminal", "GNOME Terminal", "gnome-terminal", ("linux",),
             ["--title={title}", "--working-directory={cwd}", "--", "{command}"]),
    Terminal("konsole", "Konsole", "konsole", ("linux",),
             ["-p", "tabtitle={title}", "--workdir", "{cwd}", "-e", "{command}"]),
    Terminal("xfce4-terminal", "Xfce Terminal", "xfce4-terminal", ("linux",),
             ["--title={title}", "--working-directory={cwd}", "-e", "{command}"]),
    Terminal("kitty", "kitty", "kitty", ("linux", "darwin"),
             ["--title", "{title}", "--directory", "{cwd}", "{command}"]),
    Terminal("alacritty", "Alacritty", "alacritty", ("linux", "darwin", "win32"),
             ["--title", "{title}", "--working-directory", "{cwd}", "-e", "{command}"]),
    Terminal("wezterm", "WezTerm", "wezterm", ("linux", "darwin", "win32"),
             ["start", "--cwd", "{cwd}", "--", "{command}"]),
    Terminal("xterm", "xterm", "xterm", ("linux",),
             ["-T", "{title}", "-e", "{command}"], sets_own_cwd=False),
)


class TerminalError(RuntimeError):
    """Raised with a message meant to be shown to the person, not logged and swallowed."""


def available_terminals() -> list[Terminal]:
    return [terminal for terminal in TERMINALS if terminal.available()]


def get_terminal(key: str | None) -> Terminal:
    """The chosen terminal, or the first one installed."""
    options = available_terminals()
    if not options:
        raise TerminalError("No supported terminal found. Install Windows Terminal, "
                            "or set one in Settings.")
    for terminal in options:
        if terminal.key == key:
            return terminal
    return options[0]


def build_argv(terminal: Terminal, cwd: Path, title: str, command: list[str]) -> list[str]:
    argv: list[str] = [terminal.available()]
    for part in terminal.template:
        if part == "{command}":
            argv.extend(command)
        else:
            argv.append(part.replace("{title}", title).replace("{cwd}", str(cwd)))
    return argv


def open_terminal(cwd: Path, title: str, command: list[str], key: str | None = None) -> list[str]:
    """Open a terminal window running `command` in `cwd`. Returns the argv that was used."""
    terminal = get_terminal(key)
    argv = build_argv(terminal, cwd, title, command)
    try:
        subprocess.Popen(argv, cwd=None if terminal.sets_own_cwd else str(cwd))
    except OSError as exc:
        raise TerminalError(f"Could not start {terminal.label}: {exc}") from exc
    return argv


def claude_command(prompt: str) -> list[str]:
    """The command a session runs. Fails loudly if Claude Code is not installed."""
    executable = shutil.which("claude")
    if not executable:
        raise TerminalError("Claude Code is not on PATH. Install it, or open the folder yourself.")
    return [executable, prompt]
