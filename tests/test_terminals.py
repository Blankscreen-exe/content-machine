"""Terminal recipes: what each one actually hands to the program it starts."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from cm import terminals

# Everything a prompt or title could reasonably contain that a shell might act on.
AWKWARD_PROMPT = "Read brief.md first, then help; don't skip the 'why'."
AWKWARD_TITLE = "Q&A: cheap | fast \"now\" (blog)"

# Stands in for Claude: prints exactly the arguments it received.
STAND_IN = [sys.executable, "-c", "import sys,json;print(json.dumps(sys.argv[1:]))"]


def _recipe(key: str) -> terminals.Terminal:
    return next(t for t in terminals.TERMINALS if t.key == key)


def _run_to_completion(argv: list[str]) -> list[str]:
    """Run a recipe's argv without leaving a window open, and return what the stand-in got."""
    argv = [part for part in argv if part != "-NoExit"]
    argv = ["/c" if part == "/k" else part for part in argv]
    if argv[0].lower().endswith("powershell.exe"):
        argv.insert(1, "-NoProfile")          # the person's profile can print anything
    output = subprocess.run(argv, capture_output=True, text=True, timeout=60).stdout
    return json.loads(output.strip().splitlines()[-1])


def test_argv_is_built_from_the_recipe(tmp_path):
    kitty = _recipe("kitty")
    argv = terminals.build_argv(
        terminals.Terminal(**{**kitty.__dict__, "executable": "echo"}),
        cwd=tmp_path, title="A title with spaces", command=["claude", "a prompt"],
    )
    assert "A title with spaces" in argv          # passed as one argument, no quoting needed
    assert str(tmp_path) in argv
    assert argv[-2:] == ["claude", "a prompt"]


def test_powershell_gets_one_quoted_line():
    line = terminals._powershell_line("It's done", ["C:/bin/claude.exe", "don't, then"])
    assert line == "$Host.UI.RawUI.WindowTitle = 'It''s done'; & 'C:/bin/claude.exe' 'don''t, then'"


def test_cmd_titles_cannot_start_a_second_command():
    assert terminals._cmd_safe_title("x&calc") == "x calc"
    assert terminals._cmd_safe_title('"&|<>^%!') == "Content Machine"


@pytest.mark.skipif(sys.platform != "win32" or not shutil.which("powershell.exe"),
                    reason="needs Windows PowerShell")
def test_powershell_delivers_the_prompt_intact(tmp_path):
    argv = terminals.build_argv(_recipe("powershell"), tmp_path, AWKWARD_TITLE,
                                [*STAND_IN, AWKWARD_PROMPT])
    assert _run_to_completion(argv) == [AWKWARD_PROMPT]


@pytest.mark.skipif(sys.platform != "win32" or not shutil.which("cmd.exe"),
                    reason="needs Command Prompt")
def test_cmd_delivers_the_prompt_intact_whatever_the_title(tmp_path):
    argv = terminals.build_argv(_recipe("cmd"), tmp_path, AWKWARD_TITLE,
                                [*STAND_IN, AWKWARD_PROMPT])
    assert _run_to_completion(argv) == [AWKWARD_PROMPT]
