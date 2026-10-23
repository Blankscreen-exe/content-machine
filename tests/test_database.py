"""Two processes on one content.db, as when the app and a Claude session's tools both run."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from cm.database import configure_connections

REPO = Path(__file__).resolve().parent.parent

# Says it is ready, waits for the word, then writes in many small transactions, as a batch
# filing pieces one by one would.
WRITER = """
import sys
from sqlalchemy import create_engine, text
from cm.database import configure_connections

engine = configure_connections(create_engine(f"sqlite:///{sys.argv[1]}"))
print("ready", flush=True)
sys.stdin.readline()
for n in range(200):
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO note (writer, n) VALUES (:writer, :n)"),
                           {"writer": sys.argv[2], "n": n})
"""


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "content.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE note (writer TEXT, n INTEGER)")
    connection.close()
    return path


def test_two_processes_writing_at_once_both_finish(tmp_path):
    database = _database(tmp_path)
    # the app's settings read the workspace and a .env from where they start: keep both here
    env = {**os.environ, "CM_WORKSPACE": str(tmp_path / "workspace"), "PYTHONPATH": str(REPO)}
    writers = [subprocess.Popen([sys.executable, "-c", WRITER, str(database), name], cwd=tmp_path, env=env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)
               for name in ("app", "session")]
    for writer in writers:
        assert writer.stdout.readline().strip() == "ready", writer.stderr.read()
    for writer in writers:                    # both start together, so their writes overlap
        writer.stdin.write("go\n")
        writer.stdin.flush()
    for writer in writers:
        _, errors = writer.communicate(timeout=120)
        assert writer.returncode == 0, errors

    with sqlite3.connect(database) as connection:
        counts = dict(connection.execute("SELECT writer, count(*) FROM note GROUP BY writer").fetchall())
    connection.close()
    assert counts == {"app": 200, "session": 200}


def test_a_write_in_progress_does_not_shut_readers_out(tmp_path):
    """The default journal locks readers out while a commit is written; WAL never does."""
    database = _database(tmp_path)
    engine = configure_connections(create_engine(f"sqlite:///{database}"))
    with engine.connect() as connection:          # the first connection puts the file in WAL
        connection.execute(text("INSERT INTO note VALUES ('app', 0)"))
        connection.commit()

    writer = sqlite3.connect(database, isolation_level=None)
    try:
        writer.execute("BEGIN EXCLUSIVE")         # the lock the default journal takes to commit
        writer.execute("INSERT INTO note VALUES ('session', 0)")
        reader = sqlite3.connect(database, timeout=0)   # not waiting: shut out would fail at once
        try:
            assert reader.execute("SELECT count(*) FROM note").fetchone() == (1,)
        finally:
            reader.close()
        writer.execute("COMMIT")
    finally:
        writer.close()
        engine.dispose()
