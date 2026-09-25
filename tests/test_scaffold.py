"""Starter material: the files `cm init` writes, and the text new brands and modes begin with."""
from __future__ import annotations

import pytest

from cm import scaffold
from cm.settings import get_settings


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


def test_init_creates_rules_skills_and_the_content_folder(workspace_dir):
    scaffold.init_workspace()

    assert (workspace_dir / "CLAUDE.md").exists()
    assert (workspace_dir / "content").is_dir()
    for name in ("outline", "derive", "spec", "video"):
        skill = workspace_dir / ".claude" / "skills" / name / "SKILL.md"
        assert skill.exists(), f"missing skill: {name}"
        assert skill.read_text(encoding="utf-8").startswith("---\nname:")
    assert not (workspace_dir / "brands").exists()      # brands live in the database now


def test_init_sets_up_the_video_packages_and_the_example_kit(workspace_dir):
    scaffold.init_workspace()

    # at the root, so every piece folder beneath it finds the packages
    for name in ("package.json", "package-lock.json", ".npmrc"):
        assert (workspace_dir / name).is_file(), f"missing {name}"
    kit = workspace_dir / "video" / "example-kit"
    assert (kit / "index.ts").is_file()
    assert (kit / "fonts" / "inter-latin-800-normal.woff2").read_bytes()[:4] == b"wOF2"


def test_init_never_overwrites_your_edits(workspace_dir):
    scaffold.init_workspace()
    rules = workspace_dir / "CLAUDE.md"
    rules.write_text("my own rules", encoding="utf-8")

    written = scaffold.init_workspace()

    assert written == []
    assert rules.read_text(encoding="utf-8") == "my own rules"


def test_force_rewrites_them(workspace_dir):
    scaffold.init_workspace()
    (workspace_dir / "CLAUDE.md").write_text("my own rules", encoding="utf-8")

    scaffold.init_workspace(force=True)

    assert "Never publish anything" in (workspace_dir / "CLAUDE.md").read_text(encoding="utf-8")


def test_a_new_brand_starts_from_placeholders_headed_with_its_name():
    starter = scaffold.brand_starter("Acme Co")

    assert starter["voice"].startswith("# Voice: Acme Co")
    assert starter["profile"].startswith("# Brand: Acme Co")
    for field, text in starter.items():
        assert "[Brand name]" not in text
        assert text.count("[") >= 5, f"the {field} template should be placeholders, not real content"


def test_a_new_mode_starts_from_the_questions_a_mode_answers():
    assert "The reader is" in scaffold.mode_starter()
