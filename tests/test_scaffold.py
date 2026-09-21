"""Starter files for a workspace."""
from __future__ import annotations

import pytest

from cm import scaffold
from cm.settings import get_settings


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


def test_init_creates_rules_skills_folders_and_a_starter_brand(workspace_dir):
    scaffold.init_workspace()

    assert (workspace_dir / "CLAUDE.md").exists()
    assert (workspace_dir / "content").is_dir()
    for name in ("outline", "derive", "spec"):
        skill = workspace_dir / ".claude" / "skills" / name / "SKILL.md"
        assert skill.exists(), f"missing skill: {name}"
        assert skill.read_text(encoding="utf-8").startswith("---\nname:")
    for name in ("voice.md", "brand.md"):
        assert (workspace_dir / "brands" / "example" / name).exists()


def test_init_never_overwrites_your_edits(workspace_dir):
    scaffold.init_workspace()
    voice = workspace_dir / "brands" / "example" / "voice.md"
    voice.write_text("my own voice", encoding="utf-8")

    written = scaffold.init_workspace()

    assert written == []
    assert voice.read_text(encoding="utf-8") == "my own voice"


def test_force_rewrites_them(workspace_dir):
    scaffold.init_workspace()
    (workspace_dir / "CLAUDE.md").write_text("my own rules", encoding="utf-8")

    scaffold.init_workspace(force=True)

    assert "Never publish anything" in (workspace_dir / "CLAUDE.md").read_text(encoding="utf-8")


def test_the_repo_ships_only_a_dummy_brand():
    """Real brands live in the workspace. The package carries one placeholder to copy from."""
    brands = sorted(path.name for path in (scaffold.STARTER / "brands").iterdir())
    assert brands == ["example"]

    for path in (scaffold.STARTER / "brands" / "example").iterdir():
        text = path.read_text(encoding="utf-8")
        assert "Acme Co" in text, f"{path.name} should use the made-up example name"
        assert text.count("[") >= 5, f"{path.name} should be placeholders, not real content"
