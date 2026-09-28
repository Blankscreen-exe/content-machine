"""An import adds to the work already here, and never changes what it finds.

These build real databases, through the migrations, because a merge writes rows into the
schema the app actually runs on: a fake table would let a mistake pass.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from cm import transfer

REPO = Path(__file__).resolve().parent.parent
DAY = "2026-09-21 12:00:00"          # noon, so the folder date is the same in any timezone


@pytest.fixture(scope="session")
def schema(tmp_path_factory) -> Path:
    """One database built by the migrations, copied for each workspace that needs one."""
    database = tmp_path_factory.mktemp("schema") / "content.db"
    config = Config(str(REPO / "alembic.ini"))
    config.set_main_option("script_location", str(REPO / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    return database


class Machine:
    """A workspace beside its repository, with the rows and files a person would have."""

    def __init__(self, root: Path, schema: Path) -> None:
        self.repo = root
        self.workspace = root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        shutil.copy(schema, self.workspace / "content.db")

    def _open(self) -> sqlite3.Connection:
        database = sqlite3.connect(self.workspace / "content.db")
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys = ON")
        return database

    def brand(self, slug: str, name: str = "", voice: str = "") -> int:
        with self._open() as database:
            found = database.execute("SELECT id FROM brand WHERE slug = ?", (slug,)).fetchone()
            if found:
                return found["id"]
            cursor = database.execute(
                "INSERT INTO brand (slug, name, active, voice, profile, created_at) VALUES (?,?,1,?,'',?)",
                (slug, name or slug.title(), voice, DAY))
            return int(cursor.lastrowid)

    def idea(self, brand_id: int, title: str) -> int:
        with self._open() as database:
            cursor = database.execute(
                "INSERT INTO idea (brand_id, title, angle, talking_points, notes, source, status, priority,"
                " created_at, updated_at) VALUES (?,?,'','','','','pool',2,?,?)", (brand_id, title, DAY, DAY))
            return int(cursor.lastrowid)

    def piece(self, brand_id: int, title: str, slug: str, idea_id: int | None = None,
              source_piece_id: int | None = None, kind: str = "blog", body: str = "draft") -> int:
        with self._open() as database:
            type_id = database.execute("SELECT id FROM piece_type WHERE name = ?", (kind,)).fetchone()["id"]
            cursor = database.execute(
                "INSERT INTO piece (brand_id, idea_id, type_id, source_piece_id, title, slug, stage, notes,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,'draft','',?,?)",
                (brand_id, idea_id, type_id, source_piece_id, title, slug, DAY, DAY))
            piece_id = int(cursor.lastrowid)
            brand = database.execute("SELECT slug FROM brand WHERE id = ?", (brand_id,)).fetchone()["slug"]
        folder = self.workspace / "content" / brand / f"{DAY[:10]}-{slug}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "blog.md").write_text(body, encoding="utf-8")
        return piece_id

    def published(self, piece_id: int, platform: str = "linkedin") -> None:
        with self._open() as database:
            row = database.execute("SELECT id FROM platform WHERE name = ?", (platform,)).fetchone()
            platform_id = row["id"] if row else int(database.execute(
                "INSERT INTO platform (name, active) VALUES (?, 1)", (platform,)).lastrowid)
            database.execute("INSERT INTO publication (piece_id, platform_id, url, posted_at, notes)"
                             " VALUES (?,?,'https://example.com',?,'')", (piece_id, platform_id, DAY))

    def setting(self, key: str, value: str) -> None:
        with self._open() as database:
            database.execute("INSERT OR REPLACE INTO setting (key, value) VALUES (?, ?)", (key, value))

    def rows(self, query: str, *args) -> list[sqlite3.Row]:
        with self._open() as database:
            return list(database.execute(query, args))


@pytest.fixture
def here(tmp_path, schema) -> Machine:
    machine = Machine(tmp_path / "here", schema)
    brand = machine.brand("personal", voice="how I write")
    machine.piece(brand, "Already mine", "already-mine", machine.idea(brand, "My idea"), body="mine")
    return machine


@pytest.fixture
def there(tmp_path, schema) -> Machine:
    return Machine(tmp_path / "there", schema)


def _bundle(machine: Machine, tmp_path: Path, name: str = "move.zip") -> Path:
    target = tmp_path / name
    transfer.export(machine.workspace, machine.repo, target)
    return target


# --- merging ------------------------------------------------------------------------------

def test_work_from_another_machine_joins_the_work_here(here, there, tmp_path):
    brand = there.brand("personal", voice="how I write")
    there.piece(brand, "Theirs", "theirs", there.idea(brand, "Their idea"), body="theirs")

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert done.merged.ideas == 1 and done.merged.pieces == 1
    titles = {row["title"] for row in here.rows("SELECT title FROM piece")}
    assert titles == {"Already mine", "Theirs"}
    assert (here.workspace / "content/personal/2026-09-21-theirs/blog.md").read_text(encoding="utf-8") == "theirs"
    assert (here.workspace / "content/personal/2026-09-21-already-mine/blog.md").read_text(encoding="utf-8") == "mine"


def test_a_brand_already_here_is_joined_and_keeps_what_it_says_about_itself(here, there, tmp_path):
    brand = there.brand("personal", name="Renamed over there", voice="their voice")
    there.piece(brand, "Theirs", "theirs")
    there.piece(there.brand("work"), "Work piece", "work-piece")

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert done.merged.brands_joined == ["personal"] and done.merged.brands_added == ["work"]
    brands = {row["slug"]: row for row in here.rows("SELECT slug, name, voice FROM brand")}
    assert brands["personal"]["voice"] == "how I write"        # ours, not theirs
    assert brands["personal"]["name"] == "Personal"
    assert [d for d in done.merged.differences if "voice" in d] and [d for d in done.merged.differences if "name" in d]
    landed = {(row["title"], row["brand"]) for row in here.rows(
        "SELECT p.title, b.slug AS brand FROM piece p JOIN brand b ON b.id = p.brand_id")}
    assert landed == {("Already mine", "personal"), ("Theirs", "personal"), ("Work piece", "work")}


def test_an_idea_the_brand_already_holds_is_joined_not_listed_twice(here, there, tmp_path):
    """The same idea, written the same moment: its pieces hang off the one already here."""
    brand = there.brand("personal")
    idea = there.idea(brand, "My idea")                  # same title and moment as the one here
    there.piece(brand, "New work from that idea", "new-work", idea)

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert done.merged.ideas == 0 and done.merged.ideas_already_here == 1
    assert len(here.rows("SELECT id FROM idea")) == 1
    titles = {row["title"] for row in here.rows(
        "SELECT p.title AS title FROM piece p JOIN idea i ON i.id = p.idea_id")}
    assert titles == {"Already mine", "New work from that idea"}


def test_an_idea_of_its_own_is_still_added(here, there, tmp_path):
    brand = there.brand("personal")
    there.piece(brand, "Theirs", "theirs", there.idea(brand, "A different idea"))

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert done.merged.ideas == 1
    assert {row["title"] for row in here.rows("SELECT title FROM idea")} == {"My idea", "A different idea"}


def test_the_same_piece_travelled_back_is_left_alone(here, there, tmp_path):
    """The piece here and the incoming one are the same file for file, so it is not doubled."""
    brand = there.brand("personal")
    there.piece(brand, "Already mine", "already-mine", body="mine")   # identical to the one here

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert done.merged.already_here == ["personal/2026-09-21-already-mine"]
    assert done.merged.copies == []
    assert done.merged.pieces == 0
    assert {row["slug"] for row in here.rows("SELECT slug FROM piece")} == {"already-mine"}
    assert not (here.workspace / "content/personal/2026-09-21-already-mine-2").exists()
    assert (here.workspace / "content/personal/2026-09-21-already-mine/blog.md"
            ).read_text(encoding="utf-8") == "mine"


def test_the_same_name_with_an_extra_file_is_different_work(here, there, tmp_path):
    """Same name, but the other machine added a file: that is work of its own, so it comes in."""
    brand = there.brand("personal")
    there.piece(brand, "Already mine", "already-mine", body="mine")
    (there.workspace / "content/personal/2026-09-21-already-mine/notes.md").write_text("more", encoding="utf-8")

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert done.merged.already_here == []
    assert done.merged.copies == [("personal/2026-09-21-already-mine-2", "personal/2026-09-21-already-mine")]
    assert (here.workspace / "content/personal/2026-09-21-already-mine-2/notes.md").is_file()


def test_a_piece_whose_folder_is_taken_comes_in_beside_it(here, there, tmp_path):
    brand = there.brand("personal")
    there.piece(brand, "Same name, other machine", "already-mine", body="theirs")

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert done.merged.copies == [("personal/2026-09-21-already-mine-2", "personal/2026-09-21-already-mine")]
    assert (here.workspace / "content/personal/2026-09-21-already-mine/blog.md").read_text(encoding="utf-8") == "mine"
    assert (here.workspace / "content/personal/2026-09-21-already-mine-2/blog.md").read_text(encoding="utf-8") == "theirs"
    slugs = {row["slug"] for row in here.rows("SELECT slug FROM piece")}
    assert slugs == {"already-mine", "already-mine-2"}


def test_the_next_free_name_is_taken_however_many_are_there(here, there, tmp_path):
    here.piece(here.brand("personal"), "A copy from before", "already-mine-2", body="the earlier copy")
    there.piece(there.brand("personal"), "Theirs", "already-mine", body="theirs")

    transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert {row["slug"] for row in here.rows("SELECT slug FROM piece")} == {
        "already-mine", "already-mine-2", "already-mine-3"}
    assert (here.workspace / "content/personal/2026-09-21-already-mine-3/blog.md"
            ).read_text(encoding="utf-8") == "theirs"


def test_a_folder_left_behind_on_disk_is_not_written_into(here, there, tmp_path):
    """A piece deleted here leaves its folder in place; an import must not land in it."""
    (here.workspace / "content/personal/2026-09-21-orphan").mkdir(parents=True)
    (here.workspace / "content/personal/2026-09-21-orphan/blog.md").write_text("left behind", encoding="utf-8")
    there.piece(there.brand("personal"), "Theirs", "orphan", body="theirs")

    transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert (here.workspace / "content/personal/2026-09-21-orphan/blog.md"
            ).read_text(encoding="utf-8") == "left behind"
    assert (here.workspace / "content/personal/2026-09-21-orphan-2/blog.md"
            ).read_text(encoding="utf-8") == "theirs"


def test_the_links_between_rows_still_point_where_they_should(here, there, tmp_path):
    brand = there.brand("writing")
    idea = there.idea(brand, "Their idea")
    blog = there.piece(brand, "The blog", "the-blog", idea)
    post = there.piece(brand, "The post", "the-post", idea, source_piece_id=blog, kind="linkedin post")
    there.published(post, platform="linkedin")

    transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    rows = here.rows("SELECT p.title, p.slug, i.title AS idea, t.name AS type, s.title AS made_from,"
                     " b.slug AS brand FROM piece p"
                     " LEFT JOIN idea i ON i.id = p.idea_id"
                     " JOIN piece_type t ON t.id = p.type_id"
                     " LEFT JOIN piece s ON s.id = p.source_piece_id"
                     " JOIN brand b ON b.id = p.brand_id WHERE b.slug = 'writing' ORDER BY p.id")
    assert [(r["title"], r["idea"], r["type"], r["made_from"]) for r in rows] == [
        ("The blog", "Their idea", "blog", None),
        ("The post", "Their idea", "linkedin post", "The blog"),
    ]
    published = here.rows("SELECT p.title AS piece, pl.name AS platform FROM publication pub"
                          " JOIN piece p ON p.id = pub.piece_id JOIN platform pl ON pl.id = pub.platform_id")
    assert [(r["piece"], r["platform"]) for r in published] == [("The post", "linkedin")]


def test_the_audit_trail_follows_its_own_rows(here, there, tmp_path):
    brand = there.brand("personal")
    piece = there.piece(brand, "Theirs", "theirs")
    with sqlite3.connect(there.workspace / "content.db") as database:
        database.execute("INSERT INTO event (entity, entity_id, from_state, to_state, at, note)"
                         " VALUES ('piece', ?, '', 'draft', ?, 'created')", (piece, DAY))

    transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    events = here.rows("SELECT e.entity_id, p.title FROM event e JOIN piece p ON p.id = e.entity_id"
                       " WHERE e.entity = 'piece'")
    assert [row["title"] for row in events] == ["Theirs"]


def test_a_setting_already_here_keeps_its_value_and_a_new_one_is_taken(here, there, tmp_path):
    here.setting("theme", "1996")
    there.setting("theme", "midnight")
    there.setting("due_soon_days", "14")

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    settings = {row["key"]: row["value"] for row in here.rows("SELECT key, value FROM setting")}
    assert settings == {"theme": "1996", "due_soon_days": "14"} and done.merged.settings_added == 1


def test_a_workspace_file_already_here_is_kept(here, there, tmp_path):
    (here.workspace / "CLAUDE.md").write_text("my rules", encoding="utf-8")
    (there.workspace / "CLAUDE.md").write_text("their rules", encoding="utf-8")
    (there.workspace / "resources" / "personal").mkdir(parents=True)
    (there.workspace / "resources" / "personal" / "music.txt").write_text("theirs", encoding="utf-8")

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert (here.workspace / "CLAUDE.md").read_text(encoding="utf-8") == "my rules"
    assert (here.workspace / "resources/personal/music.txt").read_text(encoding="utf-8") == "theirs"
    assert done.kept_files == 1


def test_a_personal_file_already_here_is_kept_when_merging(here, there, tmp_path):
    (here.repo / "docs").mkdir(parents=True, exist_ok=True)
    (here.repo / "docs" / "notes.md").write_text("mine", encoding="utf-8")
    (there.repo / "docs").mkdir(parents=True, exist_ok=True)
    (there.repo / "docs" / "notes.md").write_text("theirs", encoding="utf-8")

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert (here.repo / "docs" / "notes.md").read_text(encoding="utf-8") == "mine"
    assert done.kept_existing == ["docs/notes.md"]


# --- the same export twice -------------------------------------------------------------------

def test_the_same_export_is_not_imported_twice(here, there, tmp_path):
    there.piece(there.brand("personal"), "Theirs", "theirs")
    bundle = _bundle(there, tmp_path)
    transfer.import_(bundle, here.workspace, here.repo)

    with pytest.raises(transfer.TransferError, match="already imported that export"):
        transfer.import_(bundle, here.workspace, here.repo)
    assert len(here.rows("SELECT id FROM piece")) == 2          # mine, and theirs the once


def test_the_same_export_can_be_insisted_on(here, there, tmp_path):
    """`again` gets past the record of having imported it; the merge rules still apply, and
    they find every piece already here, so insisting adds nothing rather than doubling it."""
    there.piece(there.brand("personal"), "Theirs", "theirs")
    bundle = _bundle(there, tmp_path)
    transfer.import_(bundle, here.workspace, here.repo)

    done = transfer.import_(bundle, here.workspace, here.repo, again=True)

    assert done.merged.already_here == ["personal/2026-09-21-theirs"]
    assert len(here.rows("SELECT id FROM piece")) == 2
    assert not (here.workspace / "content/personal/2026-09-21-theirs-2").exists()


def test_what_this_machine_has_imported_stays_on_it(here, there, tmp_path):
    there.piece(there.brand("personal"), "Theirs", "theirs")
    transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    records = json.loads((here.workspace / ".cm" / "imports.json").read_text(encoding="utf-8"))
    assert records[0]["name"] == "move.zip" and len(records[0]["sha256"]) == 64
    onward = _bundle(here, tmp_path, "onward.zip")               # .cm never travels
    assert ".cm/imports.json" not in [n.removeprefix("workspace/") for n in __import__("zipfile")
                                      .ZipFile(onward).namelist()]


# --- an empty workspace, and an older export ---------------------------------------------------

def test_an_empty_workspace_still_takes_the_whole_export(there, tmp_path):
    brand = there.brand("personal")
    there.piece(brand, "Theirs", "theirs", there.idea(brand, "Their idea"), body="theirs")
    fresh = tmp_path / "fresh"

    done = transfer.import_(_bundle(there, tmp_path), fresh / "workspace", fresh)

    assert done.merged is None and done.files
    assert (fresh / "workspace/content/personal/2026-09-21-theirs/blog.md").read_text(encoding="utf-8") == "theirs"
    rows = sqlite3.connect(fresh / "workspace/content.db").execute("SELECT title FROM piece").fetchall()
    assert rows == [("Theirs",)]


def test_an_export_from_an_older_version_still_merges(here, there, tmp_path):
    """The export is stamped one migration back, as an older machine's would be."""
    brand = there.brand("personal")
    there.piece(brand, "Theirs", "theirs")
    config = Config(str(REPO / "alembic.ini"))
    config.set_main_option("script_location", str(REPO / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{there.workspace / 'content.db'}")
    config.attributes["configure_logger"] = False
    command.downgrade(config, "-1")

    done = transfer.import_(_bundle(there, tmp_path), here.workspace, here.repo)

    assert done.merged.pieces == 1
    assert {row["title"] for row in here.rows("SELECT title FROM piece")} == {"Already mine", "Theirs"}


def test_a_file_that_cannot_be_written_puts_the_rows_back(here, there, tmp_path, monkeypatch):
    """The rows and the files land together: if a file fails, the work here is as it was."""
    brand = there.brand("personal")
    there.piece(brand, "Theirs", "theirs", there.idea(brand, "Their idea"))
    bundle = _bundle(there, tmp_path)
    real_copy = transfer.shutil.copyfileobj
    calls = {"n": 0}

    def fail_on_the_second(source, out, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("disk full")
        return real_copy(source, out, *args, **kwargs)

    monkeypatch.setattr(transfer.shutil, "copyfileobj", fail_on_the_second)

    with pytest.raises(transfer.TransferError, match="Nothing was added to your work"):
        transfer.import_(bundle, here.workspace, here.repo)

    assert [row["title"] for row in here.rows("SELECT title FROM piece")] == ["Already mine"]
    assert not here.rows("SELECT id FROM idea WHERE title = 'Their idea'")
    assert not (here.workspace / ".cm" / "imports.json").exists()      # nothing to remember
