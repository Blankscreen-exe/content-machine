"""Moving your work to another machine: everything that is yours, in one zip.

`cm export` packs the workspace (the database, copied whole even while the app is running,
and every file: content, brand resources and kits, session rules and skills, trash) and the
personal folders kept beside the code but out of git, `docs/` and `demo/`.

It leaves out what the other machine makes for itself: installed npm packages, in any
`node_modules/`, and the app's own state in `.cm/`, which holds the access token (it must
never leave this machine), the search index, render folders and whisper.cpp.

`cm import` adds what the zip holds to this machine. Into an empty workspace it lands
whole; into one with work in it the rows are merged in beside what is already here (see
cm.merge), and a file already here is always the one that is kept. Either way the database
is brought up to the app's schema, so an export from an older version still opens.

Every import is written down in `.cm/imports.json`, which never travels, so importing the
same export twice is noticed rather than quietly doubling the work.
"""
from __future__ import annotations

import hashlib
import json
import zlib
import shutil
import sqlite3
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import merge
from .merge import Merged

FORMAT = 1
MANIFEST = "content-machine-export.json"
WORKSPACE = "workspace"
PERSONAL = "personal"
DATABASE = "content.db"
# Made again on the other machine; the token, in .cm/, must not travel at all.
STATE = ".cm"                      # only at the top of the workspace
PACKAGES = "node_modules"          # wherever it is: npm puts it back
# SQLite's side files: the database is copied whole instead.
DATABASE_SIDE_FILES = {"content.db-wal", "content.db-shm", "content.db-journal"}
# Beside the code, kept out of git as personal material (see .gitignore).
PERSONAL_FOLDERS = ("docs", "demo")
# What this machine has imported, kept in .cm/ because it never travels with an export.
IMPORTS = "imports.json"
IMPORTS_KEPT = 50


class TransferError(RuntimeError):
    """The export or import cannot go ahead; the message says why and what to do."""


@dataclass
class Imported:
    files: int = 0
    kept_existing: list[str] = field(default_factory=list)   # personal files already there, left alone
    merged: Merged | None = None                             # what joined work already here, if any
    kept_files: int = 0                                      # workspace files already here, left alone


def export(workspace: Path, repo: Path, target: Path) -> int:
    """Write everything that is yours to the zip `target`. Returns how many files it holds."""
    if target.exists():
        raise TransferError(f"{target} already exists. Choose another name, or move it away first.")
    packed = [workspace, *(repo / folder for folder in PERSONAL_FOLDERS)]
    if any(target.resolve().is_relative_to(place.resolve()) for place in packed):
        raise TransferError(f"{target} is inside what is being exported, so it would pack itself. "
                            "Save it somewhere else, such as your Downloads folder.")
    if not (workspace / DATABASE).is_file():
        raise TransferError(f"There is no {DATABASE} in {workspace}, so there is nothing to export.")
    count = 0
    partial = target.with_name(target.name + ".part")
    try:
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as bundle:
            with tempfile.TemporaryDirectory() as scratch:
                bundle.write(_snapshot(workspace / DATABASE, Path(scratch) / DATABASE), f"{WORKSPACE}/{DATABASE}")
            count += 1
            for path in _files(workspace):
                relative = path.relative_to(workspace)
                if (relative.parts[0] == STATE or PACKAGES in relative.parts
                        or relative.name in DATABASE_SIDE_FILES or relative.name == DATABASE):
                    continue
                bundle.write(path, f"{WORKSPACE}/{relative.as_posix()}")
                count += 1
            for folder in PERSONAL_FOLDERS:
                for path in _files(repo / folder):
                    if PACKAGES in path.relative_to(repo).parts:
                        continue
                    bundle.write(path, f"{PERSONAL}/{path.relative_to(repo).as_posix()}")
                    count += 1
            bundle.writestr(MANIFEST, json.dumps({
                "format": FORMAT,
                "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "files": count,
            }, indent=1))
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return count


def import_(bundle_path: Path, workspace: Path, repo: Path, again: bool = False) -> Imported:
    """Bring an export into `workspace` and the personal folders beside `repo`.

    An empty workspace takes the whole thing; one with work in it has the rows merged in.
    `again` imports an export this machine has already had.
    """
    with zipfile.ZipFile(bundle_path) as bundle:
        _check(bundle)
        fingerprint = _fingerprint(bundle_path)
        seen = _already_imported(workspace, fingerprint)
        if seen and not again:
            raise TransferError(f"This machine already imported that export, on {seen}. Importing it twice "
                                "would add a second copy of the same work. Import it again anyway with "
                                "`--again`.")
        done = Imported()
        merging = (workspace / DATABASE).exists()
        try:
            if merging:
                _merge_in(bundle, workspace, repo, done)
            else:
                _unpack(bundle, workspace, repo, done)
        except OSError as exc:
            raise TransferError(
                f"The import stopped part way ({exc}). "
                + ("Nothing was added to your work: the rows went back as they were. Some files may "
                   "have been copied into the workspace already; importing again writes the rest and "
                   "leaves them as they are." if merging else
                   f"Delete {workspace / DATABASE} and {workspace / 'content'}, then import again.")) from exc
    _remember_import(workspace, fingerprint, bundle_path)
    return done


def _merge_in(bundle: zipfile.ZipFile, workspace: Path, repo: Path, done: Imported) -> None:
    """Merge the incoming database into the one here, then copy in the files it does not have.

    Both happen inside one transaction on this machine's database: if a file cannot be
    written, the rows go back and the workspace is as it was, bar files already copied.
    """
    from .database import migrate                     # here: importing it opens the app's engine

    with tempfile.TemporaryDirectory() as scratch:
        incoming_db = Path(scratch) / DATABASE
        with bundle.open(f"{WORKSPACE}/{DATABASE}") as source, incoming_db.open("wb") as out:
            shutil.copyfileobj(source, out)
        migrate(f"sqlite:///{incoming_db}")           # an export from an older version merges too

        incoming = sqlite3.connect(incoming_db)
        live = sqlite3.connect(workspace / DATABASE, isolation_level=None)
        try:
            live.execute("PRAGMA foreign_keys = ON")
            live.execute("BEGIN IMMEDIATE")           # claim the database before any work is done
        except sqlite3.OperationalError as exc:
            incoming.close()
            live.close()
            raise TransferError("The database is in use, so nothing was imported. Close the app "
                                "(`cm serve`) and any open session, then import again.") from exc
        try:
            done.merged = merge.merge(incoming, live, workspace / "content",
                                      same_files=_folder_matcher(bundle, workspace / "content"))
            _unpack(bundle, workspace, repo, done, folders=done.merged.folders, keep_existing=True)
            live.execute("COMMIT")
        except BaseException:
            live.execute("ROLLBACK")
            raise
        finally:
            incoming.close()
            live.close()


def _folder_matcher(bundle: zipfile.ZipFile, content_dir: Path) -> "Callable[[str], bool]":
    """Tells the merge whether the export's copy of `<brand>/<folder>` is the one already here.

    A piece that travelled here in an earlier export meets itself on the way back, and doubling
    it helps nobody. Sameness is every file, its size and its checksum: the zip carries a CRC of
    each file already, so nothing has to be unpacked to find out.
    """
    packed: dict[str, dict[str, tuple[int, int]]] = {}
    prefix = f"{WORKSPACE}/content/"
    for entry in bundle.infolist():
        if entry.is_dir() or not entry.filename.startswith(prefix):
            continue
        parts = PurePosixPath(entry.filename[len(prefix):]).parts
        if len(parts) < 3:                         # brand/folder/file at the very least
            continue
        key = f"{parts[0]}/{parts[1]}"
        packed.setdefault(key, {})["/".join(parts[2:])] = (entry.file_size, entry.CRC)

    def same(folder: str) -> bool:
        here = content_dir / folder
        theirs = packed.get(folder, {})
        # Neither side holding a file is a match too: a piece nobody has opened yet has no
        # folder at all, and that is still the same piece.
        ours = ({path.relative_to(here).as_posix(): path for path in here.rglob("*") if path.is_file()}
                if here.is_dir() else {})
        if set(ours) != set(theirs):
            return False
        for name, path in ours.items():
            size, crc = theirs[name]
            if path.stat().st_size != size or _crc(path) != crc:
                return False
        return True

    return same


def _crc(path: Path) -> int:
    value = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            value = zlib.crc32(chunk, value)
    return value


def _unpack(bundle: zipfile.ZipFile, workspace: Path, repo: Path, done: Imported,
            folders: dict[str, str] | None = None, keep_existing: bool = False) -> None:
    """Write out each file. Into an empty workspace the incoming files replace a fresh
    `cm init`'s starter ones; when merging, anything already here is left as it is. A
    personal file that already exists is always kept, either way."""
    for entry in bundle.infolist():
        if entry.is_dir() or entry.filename == MANIFEST:
            continue
        section, _, rest = entry.filename.partition("/")
        if section == WORKSPACE:
            if keep_existing and rest == DATABASE:
                continue                        # merged row by row instead of copied over
            target = workspace / _placed(rest, folders)
            if keep_existing and target.exists():
                done.kept_files += 1
                continue
        else:
            target = repo / rest
            if target.exists():
                done.kept_existing.append(rest)
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with bundle.open(entry) as source, target.open("wb") as out:
            shutil.copyfileobj(source, out)
        done.files += 1


def _placed(rest: str, folders: dict[str, str] | None) -> str:
    """Where a workspace file goes here: a piece that came in beside one of ours carries its
    files into the folder it landed as, not the one it had on the other machine."""
    if not folders:
        return rest
    parts = PurePosixPath(rest).parts
    if len(parts) < 4 or parts[0] != "content":
        return rest
    landed = folders.get(f"{parts[1]}/{parts[2]}")
    return rest if landed is None else "/".join(("content", landed, *parts[3:]))


# --- imports this machine has already had ------------------------------------------------

def _fingerprint(bundle_path: Path) -> str:
    digest = hashlib.sha256()
    with bundle_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _imports_file(workspace: Path) -> Path:
    return workspace / STATE / IMPORTS


def _already_imported(workspace: Path, fingerprint: str) -> str | None:
    """When this export was imported here before, or None. An unreadable record means no: it
    is a convenience, and losing it should never stand between someone and their work."""
    try:
        records = json.loads(_imports_file(workspace).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for record in records if isinstance(records, list) else []:
        if isinstance(record, dict) and record.get("sha256") == fingerprint:
            return str(record.get("at", "an earlier day"))
    return None


def _remember_import(workspace: Path, fingerprint: str, bundle_path: Path) -> None:
    try:
        records = json.loads(_imports_file(workspace).read_text(encoding="utf-8"))
        records = records if isinstance(records, list) else []
    except (OSError, ValueError):
        records = []
    records.append({"sha256": fingerprint, "name": bundle_path.name,
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    try:
        _imports_file(workspace).parent.mkdir(parents=True, exist_ok=True)
        _imports_file(workspace).write_text(json.dumps(records[-IMPORTS_KEPT:], indent=1), encoding="utf-8")
    except OSError:
        pass                                    # the work is in; not being able to note it is not a failure


def _check(bundle: zipfile.ZipFile) -> None:
    """Refuse anything that is not an export of ours, or that would write outside its places."""
    try:
        manifest = json.loads(bundle.read(MANIFEST))
    except (KeyError, ValueError) as exc:
        raise TransferError("That zip is not a Content Machine export (it has no manifest).") from exc
    if manifest.get("format") != FORMAT:
        raise TransferError(f"That export is in format {manifest.get('format')}, and this version of the app "
                            f"reads format {FORMAT}. Update the app on one machine or the other.")
    for name in bundle.namelist():
        path = PurePosixPath(name)
        section = path.parts[0] if path.parts else ""
        allowed = (name == MANIFEST or section == WORKSPACE
                   or (section == PERSONAL and len(path.parts) > 1 and path.parts[1] in PERSONAL_FOLDERS))
        if not allowed or path.is_absolute() or ".." in path.parts or "\\" in name:
            raise TransferError(f"The export holds {name!r}, which is not somewhere an export may write. "
                                "Nothing was imported.")


def _snapshot(database: Path, target: Path) -> Path:
    """A whole copy of the database, consistent even if the app is writing to it now."""
    source = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()
    return target


def _files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else []
