"""How a session is started: restricted, our tools only, and the brand's own folders."""
from __future__ import annotations

import json

import pytest

from cm import claude_session
from cm.settings import get_settings


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    monkeypatch.setattr(claude_session.shutil, "which", lambda name: f"/bin/{name}")
    return tmp_path


def test_a_session_cannot_run_code_and_reaches_the_app_only_through_its_tools(workspace_dir):
    argv = claude_session.command("personal", "Read brief.md")

    assert argv[0] == "/bin/claude"
    assert "--restricted" in argv and "--strict-mcp-config" in argv
    assert argv[argv.index("--allowedTools") + 1] == "mcp__cm"
    assert argv[-2:] == ["--", "Read brief.md"]     # never read as one more folder or config


def test_a_session_may_touch_its_own_brand_and_nothing_else(workspace_dir):
    (workspace_dir / "video" / "example-kit").mkdir(parents=True)
    argv = claude_session.command("personal", "Read brief.md")

    folders = argv[argv.index("--add-dir") + 1:argv.index("--")]
    assert folders == [str(workspace_dir / "content" / "personal"),
                       str(workspace_dir / "resources" / "personal"),
                       str(workspace_dir / "video" / "example-kit")]
    assert all((workspace_dir / folder).is_dir() for folder in folders)   # Claude Code refuses missing ones


def test_the_tools_start_on_this_workspace_for_this_brand(workspace_dir):
    argv = claude_session.command("personal", "Read brief.md")

    config = json.loads(open(argv[argv.index("--mcp-config") + 1], encoding="utf-8").read())
    server = config["mcpServers"]["cm"]
    assert server["args"][-2:] == ["--brand", "personal"]
    assert server["env"] == {"CM_WORKSPACE": str(workspace_dir)}
    assert argv[argv.index("--mcp-config") + 1].startswith(str(workspace_dir / ".cm"))   # never exported


def test_no_claude_code_is_said_plainly(monkeypatch):
    monkeypatch.setattr(claude_session.shutil, "which", lambda name: None)
    with pytest.raises(claude_session.TerminalError, match="Claude Code is not on PATH"):
        claude_session.command("personal", "Read brief.md")
