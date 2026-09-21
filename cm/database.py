"""Engine and session handling."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from .settings import get_settings

_settings = get_settings()


def enforce_foreign_keys(target: Engine) -> Engine:
    """Make SQLite check the links between tables.

    SQLite ignores foreign keys unless each connection switches them on, so without this a
    piece could point at an idea that no longer exists and nothing would complain.
    """
    @event.listens_for(target, "connect")
    def _on_connect(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return target


# check_same_thread=False: uvicorn serves requests on a thread pool, SQLite defaults to
# refusing a connection used from more than one thread.
engine = enforce_foreign_keys(create_engine(
    _settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
))


def migrate() -> None:
    """Bring the workspace database up to the latest schema.

    Alembic owns the schema: running it on start means an older database is upgraded in
    place instead of silently missing columns.
    """
    from alembic import command
    from alembic.config import Config

    repo = Path(__file__).resolve().parent.parent
    config = Config(str(repo / "alembic.ini"))
    config.set_main_option("script_location", str(repo / "alembic"))  # independent of cwd
    config.set_main_option("sqlalchemy.url", _settings.database_url)
    config.attributes["configure_logger"] = False   # keep alembic's INFO lines out of our output
    command.upgrade(config, "head")


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
