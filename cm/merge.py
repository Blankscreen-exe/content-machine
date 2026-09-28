"""Adding another machine's work to this one's, row by row.

An export carries a whole database, so an import used to mean landing in an empty
workspace. Merging reads the incoming database instead and writes what it holds into this
one, giving every row a new id and pointing its links at wherever the rows it referred to
landed.

Nothing already here is changed. A brand, piece type, platform or mode with a name this
machine already knows is joined rather than copied, and where the incoming one describes
itself differently the difference is reported, not applied. Ideas and pieces have no name
to match on, so they are always added, with one exception: a piece whose folder name is
taken and whose files are identical to the ones here is the same piece, travelled earlier,
and is left alone. Only one that differs comes in beside it under the next free name. A
setting already set keeps its value.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .dates import local_date

# Every table an export carries, in the order rows have to land: a row is only inserted
# once the rows it points at are in and their new ids are known.
#
# alembic_version is left alone: it describes this machine's schema, not the incoming one.


@dataclass
class Merged:
    """What the merge did, for the summary the person reads."""

    brands_added: list[str] = field(default_factory=list)
    brands_joined: list[str] = field(default_factory=list)
    differences: list[str] = field(default_factory=list)      # incoming details not applied
    ideas: int = 0
    pieces: int = 0
    publications: int = 0
    settings_added: int = 0
    copies: list[tuple[str, str]] = field(default_factory=list)   # (came in as, rather than)
    already_here: list[str] = field(default_factory=list)         # same piece, same files: left alone
    ideas_already_here: int = 0                                   # same idea, joined rather than listed twice
    # content/<brand>/<folder> in the export -> where its files go here
    folders: dict[str, str] = field(default_factory=dict)


def merge(incoming: sqlite3.Connection, live: sqlite3.Connection, content_dir: Path,
          same_files: Callable[[str], bool] | None = None) -> Merged:
    """Write the rows of `incoming` into `live`. The caller owns the transaction, so a
    failure anywhere leaves this machine's database as it was.

    `same_files("<brand>/<folder>")` says whether the export's copy of that folder holds
    exactly what this machine's copy holds; without it every clash is treated as different.
    """
    incoming.row_factory = sqlite3.Row
    live.row_factory = sqlite3.Row
    done = Merged()

    types = _join_by_name(incoming, live, "piece_type")
    platforms = _join_by_name(incoming, live, "platform")
    brands = _join_brands(incoming, live, done)
    modes = _join_modes(incoming, live, brands)
    ideas = _add_ideas(incoming, live, brands, modes, done)
    pieces = _add_pieces(incoming, live, brands, ideas, types, content_dir, done, same_files)
    _add_publications(incoming, live, pieces, platforms, done)
    _add_events(incoming, live, ideas, pieces)
    _add_settings(incoming, live, done)
    return done


# --- the lists everyone shares -----------------------------------------------------------

def _join_by_name(incoming: sqlite3.Connection, live: sqlite3.Connection, table: str) -> dict[int, int]:
    """Piece types and platforms: one name means one row, however it is capitalised."""
    mapping: dict[int, int] = {}
    for row in incoming.execute(f"SELECT * FROM {table}"):
        found = live.execute(f"SELECT id FROM {table} WHERE lower(trim(name)) = lower(trim(?))",
                             (row["name"],)).fetchone()
        mapping[row["id"]] = found["id"] if found else _insert(live, table, row)
    return mapping


def _join_brands(incoming: sqlite3.Connection, live: sqlite3.Connection, done: Merged) -> dict[int, int]:
    """A brand is its slug: the same slug is the same brand, and its folders are already named
    after it. What the other machine says about it is only reported, never written over."""
    mapping: dict[int, int] = {}
    for row in incoming.execute("SELECT * FROM brand"):
        found = live.execute("SELECT * FROM brand WHERE slug = ?", (row["slug"],)).fetchone()
        if found is None:
            mapping[row["id"]] = _insert(live, "brand", row)
            done.brands_added.append(row["slug"])
            continue
        mapping[row["id"]] = found["id"]
        done.brands_joined.append(row["slug"])
        for column in ("name", "voice", "profile"):
            if (row[column] or "") != (found[column] or ""):
                done.differences.append(f"{row['slug']}: its {column} differs; kept the one here")
    return mapping


def _join_modes(incoming: sqlite3.Connection, live: sqlite3.Connection,
                brands: dict[int, int]) -> dict[int, int]:
    """A mode belongs to a brand, so the same name under the same brand is the same mode."""
    mapping: dict[int, int] = {}
    for row in incoming.execute("SELECT * FROM mode"):
        brand_id = brands[row["brand_id"]]
        found = live.execute("SELECT id FROM mode WHERE brand_id = ? AND lower(trim(name)) = lower(trim(?))",
                             (brand_id, row["name"])).fetchone()
        mapping[row["id"]] = found["id"] if found else _insert(live, "mode", row, brand_id=brand_id)
    return mapping


# --- the work itself ----------------------------------------------------------------------

def _add_ideas(incoming: sqlite3.Connection, live: sqlite3.Connection, brands: dict[int, int],
               modes: dict[int, int], done: Merged) -> dict[int, int]:
    """An idea the brand already holds - same title, written the same moment - is the one that
    travelled here before, so it is joined rather than listed twice; its pieces then hang off
    the idea already here."""
    mapping: dict[int, int] = {}
    for row in incoming.execute("SELECT * FROM idea ORDER BY id"):
        brand_id = brands[row["brand_id"]]
        found = live.execute("SELECT id FROM idea WHERE brand_id = ? AND title = ? AND created_at = ?",
                             (brand_id, row["title"], row["created_at"])).fetchone()
        if found:
            mapping[row["id"]] = found["id"]
            done.ideas_already_here += 1
            continue
        mode_id = modes.get(row["mode_id"]) if row["mode_id"] is not None else None
        mapping[row["id"]] = _insert(live, "idea", row, brand_id=brand_id, mode_id=mode_id)
        done.ideas += 1
    return mapping


def _add_pieces(incoming: sqlite3.Connection, live: sqlite3.Connection, brands: dict[int, int],
                ideas: dict[int, int], types: dict[int, int], content_dir: Path,
                done: Merged, same_files: Callable[[str], bool] | None = None) -> dict[int, int]:
    """Pieces land one by one, each with a folder name that is free here.

    A clash where the files match is the piece that travelled here earlier, so it is left
    alone rather than doubled. `source_piece_id` is filled in afterwards: a piece can be made
    from one that has not landed yet, and the new id is only known once it has.
    """
    mapping: dict[int, int] = {}
    taken = _folders_in_use(live, content_dir)
    sources: dict[int, int] = {}

    for row in incoming.execute("SELECT * FROM piece ORDER BY id"):
        brand_id = brands[row["brand_id"]]
        brand = live.execute("SELECT slug FROM brand WHERE id = ?", (brand_id,)).fetchone()["slug"]
        wanted = _folder_name(row["created_at"], row["slug"])
        if (same_files is not None and wanted in taken.setdefault(brand, set())
                and _piece_here(live, brand_id, row) and same_files(f"{brand}/{wanted}")):
            done.already_here.append(f"{brand}/{wanted}")
            continue                                    # its publications and events stay with the piece here
        slug, folder = _free_folder(row, taken.setdefault(brand, set()))
        taken[brand].add(folder)
        if folder != _folder_name(row["created_at"], row["slug"]):
            done.copies.append((f"{brand}/{folder}", f"{brand}/{_folder_name(row['created_at'], row['slug'])}"))
        done.folders[f"{brand}/{_folder_name(row['created_at'], row['slug'])}"] = f"{brand}/{folder}"

        idea_id = ideas.get(row["idea_id"]) if row["idea_id"] is not None else None
        new_id = _insert(live, "piece", row, brand_id=brand_id, idea_id=idea_id,
                         type_id=types[row["type_id"]], slug=slug, source_piece_id=None)
        mapping[row["id"]] = new_id
        if row["source_piece_id"] is not None:
            sources[new_id] = row["source_piece_id"]
        done.pieces += 1

    for new_id, old_source in sources.items():
        if old_source in mapping:
            live.execute("UPDATE piece SET source_piece_id = ? WHERE id = ?", (mapping[old_source], new_id))
    return mapping


def _add_publications(incoming: sqlite3.Connection, live: sqlite3.Connection, pieces: dict[int, int],
                      platforms: dict[int, int], done: Merged) -> None:
    for row in incoming.execute("SELECT * FROM publication ORDER BY id"):
        if row["piece_id"] not in pieces:
            continue                            # its piece did not come across; nothing to hang it on
        _insert(live, "publication", row, piece_id=pieces[row["piece_id"]],
                platform_id=platforms[row["platform_id"]])
        done.publications += 1


def _add_events(incoming: sqlite3.Connection, live: sqlite3.Connection, ideas: dict[int, int],
                pieces: dict[int, int]) -> None:
    """The audit trail follows its rows. An event about something that did not come across is
    dropped, as its id here would point at a different thing entirely."""
    for row in incoming.execute("SELECT * FROM event ORDER BY id"):
        mapping = {"idea": ideas, "piece": pieces}.get(row["entity"])
        if mapping is None or row["entity_id"] not in mapping:
            continue
        _insert(live, "event", row, entity_id=mapping[row["entity_id"]])


def _add_settings(incoming: sqlite3.Connection, live: sqlite3.Connection, done: Merged) -> None:
    """Preferences are this machine's own: only a key it has never set is taken."""
    here = {row["key"] for row in live.execute("SELECT key FROM setting")}
    for row in incoming.execute("SELECT * FROM setting"):
        if row["key"] in here:
            continue
        live.execute("INSERT INTO setting (key, value) VALUES (?, ?)", (row["key"], row["value"]))
        done.settings_added += 1


# --- folders ------------------------------------------------------------------------------

def _folder_name(created_at: str, slug: str) -> str:
    """`<created date>-<slug>`, the same name cm.workspace builds a piece's folder from."""
    return f"{local_date(_moment(created_at)).isoformat()}-{slug}"


def _moment(stored: str | datetime) -> datetime:
    if isinstance(stored, datetime):
        return stored
    return datetime.fromisoformat(str(stored))


def _piece_here(live: sqlite3.Connection, brand_id: int, row: sqlite3.Row) -> bool:
    """Whether this brand already holds that same piece: same slug, same title.

    The folder name alone is not enough to leave an incoming piece out. A name can be taken by
    a folder left behind, or by a piece that only shares a title's slug, and dropping the
    incoming row then loses work. Matching the title as well keeps that to the real case.
    """
    found = live.execute("SELECT title FROM piece WHERE brand_id = ? AND slug = ?",
                         (brand_id, row["slug"])).fetchone()
    return found is not None and found["title"] == row["title"]


def _folders_in_use(live: sqlite3.Connection, content_dir: Path) -> dict[str, set[str]]:
    """The folder names already spoken for, per brand: those of the pieces here, and whatever
    is on disk — a folder left behind by a piece since deleted still holds files."""
    in_use: dict[str, set[str]] = {}
    for row in live.execute("SELECT b.slug AS slug, p.created_at AS created_at, p.slug AS piece_slug "
                            "FROM piece p JOIN brand b ON b.id = p.brand_id"):
        in_use.setdefault(row["slug"], set()).add(_folder_name(row["created_at"], row["piece_slug"]))
    if content_dir.is_dir():
        for brand_dir in content_dir.iterdir():
            if brand_dir.is_dir():
                in_use.setdefault(brand_dir.name, set()).update(p.name for p in brand_dir.iterdir() if p.is_dir())
    return in_use


def _free_folder(row: sqlite3.Row, taken: set[str]) -> tuple[str, str]:
    """(slug, folder name) for an incoming piece: its own, or the next free one beside it.

    The folder name is built from the slug, so a copy needs a slug of its own — and the slug
    is what the folder is named after for good, however the piece is retitled later.
    """
    slug, number = row["slug"], 2
    folder = _folder_name(row["created_at"], slug)
    while folder in taken:
        slug = f"{row['slug']}-{number}"
        folder = _folder_name(row["created_at"], slug)
        number += 1
    return slug, folder


# --- writing rows ---------------------------------------------------------------------------

def _insert(live: sqlite3.Connection, table: str, row: sqlite3.Row, **replace: object) -> int:
    """Insert `row` under a new id, with `replace` overriding the columns that point elsewhere.

    Only columns this machine's schema has are written: both databases are brought up to the
    same schema first, so this is a guard rather than a translation.
    """
    available = set(row.keys())
    columns = [name for name in _columns(live, table)
               if name != "id" and (name in available or name in replace)]
    values = [replace[name] if name in replace else row[name] for name in columns]
    placeholders = ", ".join("?" * len(columns))
    cursor = live.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", values)
    return int(cursor.lastrowid)


def _columns(database: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in database.execute(f"PRAGMA table_info({table})")]
