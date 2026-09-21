"""Full-text search over the drafts in piece folders, with SQLite's FTS5.

Drafts are files, and terminal sessions change them behind the app's back, so the index
is a cache that catches up before every search: a file whose size or modification time
changed is read again, and a file or piece that is gone is dropped. Nothing has to
remember to update it.

It lives in its own database, `.cm/search.db`, not in content.db: it is derived from the
files and holds nothing of its own, so deleting it only means the next search rebuilds
it, and it never needs a migration.
"""
from __future__ import annotations

import html
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from . import crud, files, workspace
from .models import Piece
from .settings import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS indexed (
    piece_id INTEGER NOT NULL, name TEXT NOT NULL, mtime_ns INTEGER NOT NULL, size INTEGER NOT NULL,
    PRIMARY KEY (piece_id, name)
);
-- porter: "queues" finds "queue"; unicode61: accents and case do not matter
CREATE VIRTUAL TABLE IF NOT EXISTS drafts USING fts5(
    piece_id UNINDEXED, name UNINDEXED, body, tokenize = 'porter unicode61'
);
"""

# Marks the matched words in a snippet. Control characters survive escaping and are then
# swapped for <mark>; they are taken out of drafts as they are indexed, so the only ones
# in a snippet are these.
MARK_START, MARK_END = "\x02", "\x03"
MAX_HITS = 50


@dataclass(frozen=True)
class Hit:
    piece: Piece
    name: str             # the draft file the words were found in
    snippet: str          # HTML: a few words either side, matches in <mark>, everything else escaped


def search(session: Session, text: str, brand_id: int | None = None) -> list[Hit]:
    """Drafts containing every word of `text`, best matches first. The last word may be
    unfinished, so results appear while typing."""
    query = _match_expression(text)
    if not query:
        return []
    with closing(_connect()) as connection:
        refresh(session, connection)
        rows = connection.execute(
            "SELECT piece_id, name, snippet(drafts, 2, ?, ?, ' … ', 16) FROM drafts "
            "WHERE drafts MATCH ? ORDER BY rank",
            (MARK_START, MARK_END, query)).fetchall()

    hits = []
    for piece_id, name, snippet in rows:
        piece = crud.get_piece(session, piece_id)
        if piece and (brand_id is None or piece.brand_id == brand_id):
            hits.append(Hit(piece, name, _highlight(snippet)))
        if len(hits) == MAX_HITS:
            break
    return hits


def refresh(session: Session, connection: sqlite3.Connection) -> None:
    """Bring the index in line with the draft files on disk."""
    on_disk = _draft_files(session)
    known = {(piece_id, name): (mtime, size) for piece_id, name, mtime, size
             in connection.execute("SELECT piece_id, name, mtime_ns, size FROM indexed")}

    for key in known.keys() - on_disk.keys():
        _forget(connection, key)
    for key, (path, mtime, size) in on_disk.items():
        if known.get(key) == (mtime, size):
            continue
        _forget(connection, key)
        piece_id, name = key
        body = path.read_text(encoding="utf-8", errors="replace")
        body = body.replace(MARK_START, "").replace(MARK_END, "")
        connection.execute("INSERT INTO drafts (piece_id, name, body) VALUES (?, ?, ?)",
                           (piece_id, name, body))
        connection.execute("INSERT INTO indexed VALUES (?, ?, ?, ?)", (piece_id, name, mtime, size))
    connection.commit()


def _draft_files(session: Session) -> dict[tuple[int, str], tuple[Path, int, int]]:
    """Every draft on disk, keyed by (piece, file name): the brief is generated, so it is left out."""
    found = {}
    for piece in crud.list_pieces(session):
        folder = workspace.piece_folder(session, piece)
        if not folder.is_dir():
            continue
        for path in folder.glob("*.md"):
            if path.name in files.GENERATED_FILES:
                continue
            stat = path.stat()
            found[(piece.id, path.name)] = (path, stat.st_mtime_ns, stat.st_size)
    return found


def _forget(connection: sqlite3.Connection, key: tuple[int, str]) -> None:
    connection.execute("DELETE FROM drafts WHERE piece_id = ? AND name = ?", key)
    connection.execute("DELETE FROM indexed WHERE piece_id = ? AND name = ?", key)


def _connect() -> sqlite3.Connection:
    path = get_settings().state_dir / "search.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    return connection


def _match_expression(text: str) -> str:
    """Words only, each quoted, so nothing typed can be read as FTS5 query syntax."""
    words = re.findall(r"\w+", text)
    if not words:
        return ""
    return " ".join(f'"{word}"' for word in words) + "*"


def _highlight(snippet: str) -> str:
    """Escape the draft's text, then mark the matches: a draft can contain anything,
    including HTML, and only the marks may reach the page as markup."""
    return html.escape(snippet).replace(MARK_START, "<mark>").replace(MARK_END, "</mark>")
