"""Opening a terminal in a piece's folder.

Each terminal gets a recipe: how to set the working folder, how to set the window or tab
title, and where the command goes. Supporting another one means adding an entry here.

Arguments are passed as a list and never through a shell, so titles and prompts with
spaces need no quoting — except where the terminal *is* a shell that reads its arguments
as code (PowerShell, Command Prompt). Those recipes carry a hook that prepares the text
for that shell, and each hook says why.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


def _powershell_line(title: str, command: list[str]) -> str:
    """PowerShell reads everything after -Command as PowerShell code, so hand it one line.

    Left as separate arguments, it re-splits them at spaces, runs anything after a `;`
    as its own statement, and turns "first, then" into a list. Single quotes are literal
    in PowerShell, with a quote inside written as two.
    """
    def quote(text: str) -> str:
        return "'" + text.replace("'", "''") + "'"

    return f"$Host.UI.RawUI.WindowTitle = {quote(title)}; & " + " ".join(quote(part) for part in command)


def _cmd_safe_title(title: str) -> str:
    """Command Prompt parses the title too: `&` would start a second command, `|` a pipe.

    The title is only cosmetic, so its special characters are dropped rather than escaped.
    """
    return re.sub(r"\s+", " ", re.sub(r'[&|<>^%!"]', " ", title)).strip() or "Content Machine"


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
    # For shells that read their arguments as code: turn (title, command) into one argument.
    join: Callable[[str, list[str]], str] | None = None
    # For shells that parse the title: make it safe to appear there.
    clean_title: Callable[[str], str] | None = None

    def available(self) -> str | None:
        if sys.platform not in self.platforms:
            return None
        return shutil.which(self.executable)


TERMINALS: tuple[Terminal, ...] = (
    Terminal("wt", "Windows Terminal", "wt.exe", ("win32",),
             ["new-tab", "--title", "{title}", "--startingDirectory", "{cwd}", "{command}"]),
    Terminal("powershell", "PowerShell", "powershell.exe", ("win32",),
             ["-NoExit", "-Command", "{command}"], sets_own_cwd=False, join=_powershell_line),
    Terminal("cmd", "Command Prompt", "cmd.exe", ("win32",),
             ["/k", "title", "{title}", "&", "{command}"], sets_own_cwd=False,
             clean_title=_cmd_safe_title),
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
    if terminal.clean_title:
        title = terminal.clean_title(title)
    argv: list[str] = [terminal.available()]
    for part in terminal.template:
        if part == "{command}":
            if terminal.join:
                argv.append(terminal.join(title, command))
            else:
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
