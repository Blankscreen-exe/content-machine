"""Migrations must actually run.

A migration that imports something it does not declare fails only at upgrade time, which
in this app happens during startup — the server dies before it serves anything.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlmodel import SQLModel

REPO = Path(__file__).resolve().parent.parent


def test_migrations_build_the_whole_schema(tmp_path: Path):
    db = tmp_path / "content.db"
    config = Config(str(REPO / "alembic.ini"))
    config.set_main_option("script_location", str(REPO / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db}")

    command.upgrade(config, "head")

    tables = {
        row[0]
        for row in sqlite3.connect(db).execute(
            "select name from sqlite_master where type='table'"
        )
    }
    expected = set(SQLModel.metadata.tables) | {"alembic_version"}
    assert expected <= tables, f"missing tables: {expected - tables}"


def _config(db: Path) -> Config:
    config = Config(str(REPO / "alembic.ini"))
    config.set_main_option("script_location", str(REPO / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    return config


def test_the_migrated_schema_matches_the_models(tmp_path: Path):
    """A column changed in a model but not in a migration would only show up on a real database."""
    config = _config(tmp_path / "content.db")
    command.upgrade(config, "head")
    command.check(config)          # raises if autogenerate would find anything to change


BEFORE_MANAGED_LISTS = "474b296587a9"


def test_existing_types_platforms_modes_and_brand_files_carry_over(tmp_path: Path):
    db = tmp_path / "content.db"
    config = _config(db)
    command.upgrade(config, BEFORE_MANAGED_LISTS)

    with sqlite3.connect(db) as connection:
        connection.executescript("""
            INSERT INTO brand (id, slug, name, active, created_at) VALUES (1, 'acme', 'Acme Co', 1, '2026-01-01');
            INSERT INTO idea (id, brand_id, title, angle, talking_points, mode, notes, source, status,
                              priority, created_at, updated_at)
              VALUES (1, 1, 'One', '', '', 'advisor', '', '', 'pool', 2, '2026-01-01', '2026-01-01'),
                     (2, 1, 'Two', '', '', ' Advisor ', '', '', 'pool', 2, '2026-01-01', '2026-01-01'),
                     (3, 1, 'Three', '', '', '', '', '', 'pool', 2, '2026-01-01', '2026-01-01');
            INSERT INTO piece (id, brand_id, idea_id, type, title, slug, stage, notes, created_at, updated_at)
              VALUES (1, 1, 1, 'linkedin', 'One', 'one-linkedin-post', 'published', '', '2026-01-01', '2026-01-01');
            INSERT INTO publication (id, piece_id, platform, url, posted_at, notes)
              VALUES (1, 1, 'LinkedIn', '', '2026-01-02', ''), (2, 1, ' linkedin', '', '2026-01-03', '');
        """)
    (tmp_path / "brands" / "acme").mkdir(parents=True)
    (tmp_path / "brands" / "acme" / "voice.md").write_text("# Voice: Acme Co", encoding="utf-8")

    command.upgrade(config, "head")

    with sqlite3.connect(db) as connection:
        piece_type = connection.execute(
            "SELECT piece_type.name, main_file FROM piece JOIN piece_type ON piece_type.id = piece.type_id"
        ).fetchone()
        platforms = connection.execute("SELECT name FROM platform").fetchall()
        used_platforms = connection.execute("SELECT DISTINCT platform_id FROM publication").fetchall()
        modes = connection.execute("SELECT brand_id, name, description FROM mode").fetchall()
        idea_modes = connection.execute("SELECT id, mode_id FROM idea ORDER BY id").fetchall()
        brand = connection.execute("SELECT voice, profile FROM brand").fetchone()

    assert piece_type == ("linkedin post", "linkedin.md")    # same type, same draft file
    assert platforms == [("LinkedIn",)] and len(used_platforms) == 1   # one spelling
    assert modes == [(1, "advisor", "")]
    assert idea_modes == [(1, 1), (2, 1), (3, None)]
    assert brand == ("# Voice: Acme Co", "")                  # no brand.md, so no profile
    assert (tmp_path / "brands" / "acme" / "voice.md").exists()   # the file is left alone

    command.downgrade(config, BEFORE_MANAGED_LISTS)
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT type FROM piece").fetchone() == ("linkedin",)
        assert connection.execute("SELECT mode FROM idea WHERE id = 1").fetchone() == ("advisor",)


def test_platform_limits_are_filled_in_for_the_seeded_types(tmp_path: Path):
    db = tmp_path / "content.db"
    command.upgrade(_config(db), "head")
    with sqlite3.connect(db) as connection:
        limits = dict(connection.execute("SELECT name, char_limit FROM piece_type").fetchall())
    assert limits["linkedin post"] == 3000 and limits["x post"] == 280 and limits["blog"] is None


BEFORE_VIDEO = "d0e86772b04c"


def test_existing_types_stay_text_and_a_short_type_is_added(tmp_path: Path):
    db = tmp_path / "content.db"
    command.upgrade(_config(db), "head")
    with sqlite3.connect(db) as connection:
        video = dict(connection.execute("SELECT name, video FROM piece_type").fetchall())
        main_file = connection.execute(
            "SELECT main_file FROM piece_type WHERE name = 'youtube short'").fetchone()
    assert video.pop("youtube short") == 1 and main_file == ("frames.md",)
    assert set(video.values()) == {0}


def test_a_short_type_already_made_by_hand_is_not_added_twice(tmp_path: Path):
    db = tmp_path / "content.db"
    config = _config(db)
    command.upgrade(config, BEFORE_VIDEO)
    with sqlite3.connect(db) as connection:
        connection.execute("INSERT INTO piece_type (name, main_file, active) VALUES ('YouTube Short', 'short.md', 1)")

    command.upgrade(config, "head")

    with sqlite3.connect(db) as connection:
        rows = connection.execute(
            "SELECT name, main_file FROM piece_type WHERE lower(name) = 'youtube short'").fetchall()
    assert rows == [("YouTube Short", "short.md")]      # yours is kept as you made it
