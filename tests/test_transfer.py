"""Moving work between machines: all of it arrives, nothing private leaves, nothing is overwritten."""
from __future__ import annotations

import json
import sqlite3
import zipfile

import pytest

from cm import transfer


@pytest.fixture
def here(tmp_path):
    """A workspace with work in it, and the repository it sits beside."""
    repo = tmp_path / "here"
    workspace = repo / "workspace"
    workspace.mkdir(parents=True)
    database = sqlite3.connect(workspace / "content.db")
    database.execute("CREATE TABLE piece (title TEXT)")
    database.execute("INSERT INTO piece VALUES ('AI prototype to production')")
    database.commit()
    database.close()
    files = {
        "content/personal/short/frames.md": "## Hook\nScript: Hi.",
        "content/personal/short/voice/take-1.webm": "voice",
        "resources/personal/kit/tokens.ts": "export const color = {};",
        ".claude/skills/video/SKILL.md": "---\nname: video\n---",
        "CLAUDE.md": "my rules",
        ".cm/token": "secret-token",
        ".cm/whisper/ggml-base.en.bin": "model",
        "node_modules/remotion/package.json": "{}",
    }
    for name, text in files.items():
        (workspace / name).parent.mkdir(parents=True, exist_ok=True)
        (workspace / name).write_text(text, encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "improvements.md").write_text("- [ ] next", encoding="utf-8")
    (repo / "demo" / "node_modules" / "roughjs").mkdir(parents=True)
    (repo / "demo" / "node_modules" / "roughjs" / "index.js").write_text("installed", encoding="utf-8")
    (repo / "demo" / "package.json").write_text("{}", encoding="utf-8")
    return repo, workspace


def _export(here, tmp_path) -> tuple:
    repo, workspace = here
    bundle = tmp_path / "move.zip"
    transfer.export(workspace, repo, bundle)
    return bundle, zipfile.ZipFile(bundle).namelist()


def test_the_export_holds_the_work_and_the_personal_notes(here, tmp_path):
    _, names = _export(here, tmp_path)
    for name in ("workspace/content.db", "workspace/content/personal/short/frames.md",
                 "workspace/content/personal/short/voice/take-1.webm", "workspace/resources/personal/kit/tokens.ts",
                 "workspace/.claude/skills/video/SKILL.md", "workspace/CLAUDE.md", "personal/docs/improvements.md",
                 transfer.MANIFEST):
        assert name in names, name


def test_the_token_and_what_is_made_again_are_left_behind(here, tmp_path):
    _, names = _export(here, tmp_path)
    assert not [n for n in names if n.startswith("workspace/.cm/") or "/node_modules/" in n]
    assert "personal/demo/package.json" in names          # the project stays; its installed packages do not


def test_everything_arrives_on_the_other_machine(here, tmp_path):
    bundle, _ = _export(here, tmp_path)
    there = tmp_path / "there"
    workspace = there / "workspace"
    workspace.mkdir(parents=True)

    done = transfer.import_(bundle, workspace, there)

    assert (workspace / "content/personal/short/frames.md").read_text(encoding="utf-8") == "## Hook\nScript: Hi."
    assert (there / "docs" / "improvements.md").read_text(encoding="utf-8") == "- [ ] next"
    rows = sqlite3.connect(workspace / "content.db").execute("SELECT title FROM piece").fetchall()
    assert rows == [("AI prototype to production",)]
    assert not (workspace / ".cm").exists() and done.files == 8


def test_the_database_is_copied_whole_even_while_it_is_open(here, tmp_path):
    repo, workspace = here
    writer = sqlite3.connect(workspace / "content.db")
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("INSERT INTO piece VALUES ('written just now')")
    writer.commit()                                   # in the WAL file, not yet in content.db itself
    bundle = tmp_path / "move.zip"
    transfer.export(workspace, repo, bundle)
    writer.close()

    snapshot = tmp_path / "snapshot.db"
    snapshot.write_bytes(zipfile.ZipFile(bundle).read("workspace/content.db"))
    assert len(sqlite3.connect(snapshot).execute("SELECT * FROM piece").fetchall()) == 2
    assert "workspace/content.db-wal" not in zipfile.ZipFile(bundle).namelist()


def test_an_import_never_lands_on_work(here, tmp_path):
    bundle, _ = _export(here, tmp_path)
    repo, workspace = here
    with pytest.raises(transfer.TransferError, match="already has work in it"):
        transfer.import_(bundle, workspace, repo)


def test_a_personal_file_already_there_is_kept(here, tmp_path):
    bundle, _ = _export(here, tmp_path)
    there = tmp_path / "there"
    (there / "docs").mkdir(parents=True)
    (there / "docs" / "improvements.md").write_text("mine, newer", encoding="utf-8")

    done = transfer.import_(bundle, there / "workspace", there)

    assert (there / "docs" / "improvements.md").read_text(encoding="utf-8") == "mine, newer"
    assert done.kept_existing == ["docs/improvements.md"]


def test_an_export_cannot_be_saved_inside_what_it_packs(here):
    repo, workspace = here
    for inside in (workspace / "move.zip", repo / "docs" / "move.zip"):
        with pytest.raises(transfer.TransferError, match="it would pack itself"):
            transfer.export(workspace, repo, inside)


def test_an_existing_zip_is_not_overwritten(here, tmp_path):
    repo, workspace = here
    (tmp_path / "move.zip").write_bytes(b"something else")
    with pytest.raises(transfer.TransferError, match="already exists"):
        transfer.export(workspace, repo, tmp_path / "move.zip")


@pytest.mark.parametrize("name", ["../escape.txt", "workspace/../../escape.txt", "personal/secrets/x.txt",
                                  "elsewhere/x.txt", "/absolute.txt"])
def test_a_zip_that_would_write_anywhere_else_is_refused_whole(tmp_path, name):
    bundle = tmp_path / "odd.zip"
    with zipfile.ZipFile(bundle, "w") as z:
        z.writestr(transfer.MANIFEST, json.dumps({"format": transfer.FORMAT}))
        z.writestr("workspace/content/fine.md", "fine")
        z.writestr(name, "nope")
    with pytest.raises(transfer.TransferError, match="not somewhere an export may write"):
        transfer.import_(bundle, tmp_path / "ws", tmp_path / "repo")
    assert not (tmp_path / "ws").exists()                # nothing written before the check


def test_a_zip_that_is_not_an_export_or_is_from_another_format_is_refused(tmp_path):
    plain = tmp_path / "plain.zip"
    with zipfile.ZipFile(plain, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(transfer.TransferError, match="not a Content Machine export"):
        transfer.import_(plain, tmp_path / "ws", tmp_path)
    later = tmp_path / "later.zip"
    with zipfile.ZipFile(later, "w") as z:
        z.writestr(transfer.MANIFEST, json.dumps({"format": transfer.FORMAT + 1}))
    with pytest.raises(transfer.TransferError, match="Update the app"):
        transfer.import_(later, tmp_path / "ws", tmp_path)
