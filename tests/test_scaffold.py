"""Starter files for a workspace."""
from __future__ import annotations

import pytest

from cm import scaffold
from cm.settings import get_settings


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


def test_init_creates_rules_skills_and_folders(workspace_dir):
    scaffold.init_workspace()

    assert (workspace_dir / "CLAUDE.md").exists()
    assert (workspace_dir / "brands").is_dir()
    assert (workspace_dir / "content").is_dir()
    for name in ("outline", "derive", "spec"):
        skill = workspace_dir / ".claude" / "skills" / name / "SKILL.md"
        assert skill.exists(), f"missing skill: {name}"
        assert skill.read_text(encoding="utf-8").startswith("---\nname:")


def test_init_never_overwrites_your_edits(workspace_dir):
    scaffold.init_workspace()
    claude_md = workspace_dir / "CLAUDE.md"
    claude_md.write_text("my own rules", encoding="utf-8")

    written = scaffold.init_workspace()

    assert written == []
    assert claude_md.read_text(encoding="utf-8") == "my own rules"


def test_force_rewrites_them(workspace_dir):
    scaffold.init_workspace()
    (workspace_dir / "CLAUDE.md").write_text("my own rules", encoding="utf-8")

    scaffold.init_workspace(force=True)

    assert "Never publish anything" in (workspace_dir / "CLAUDE.md").read_text(encoding="utf-8")
