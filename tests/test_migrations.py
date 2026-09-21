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
