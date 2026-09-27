"""Moving your work to another machine: everything that is yours, in one zip.

`cm export` packs the workspace (the database, copied whole even while the app is running,
and every file: content, brand resources and kits, session rules and skills, trash) and the
personal folders kept beside the code but out of git, `docs/` and `demo/`.

It leaves out what the other machine makes for itself: installed npm packages, in any
`node_modules/`, and the app's own state in `.cm/`, which holds the access token (it must
never leave this machine), the search index, render folders and whisper.cpp.

`cm import` unpacks it into an empty workspace only, never over one with work in it, and
never over a personal file that already exists. It then brings the database up to the
app's schema, so an export from an older version still opens.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

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


class TransferError(RuntimeError):
    """The export or import cannot go ahead; the message says why and what to do."""


@dataclass
class Imported:
    files: int = 0
    kept_existing: list[str] = field(default_factory=list)   # personal files already there, left alone


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


def import_(bundle_path: Path, workspace: Path, repo: Path) -> Imported:
    """Unpack an export into `workspace`, which must hold no work, and the personal folders
    beside `repo`. The caller brings the database up to date afterwards."""
    if (workspace / DATABASE).exists() or any((workspace / "content").glob("*")):
        raise TransferError(f"The workspace at {workspace} already has work in it, and an import never "
                            "overwrites work. Import into an empty one: set CM_WORKSPACE to a new folder, "
                            "or move this one aside.")
    with zipfile.ZipFile(bundle_path) as bundle:
        _check(bundle)
        done = Imported()
        try:
            _unpack(bundle, workspace, repo, done)
        except OSError as exc:
            raise TransferError(f"The import stopped part way ({exc}). Delete {workspace / DATABASE} and "
                                f"{workspace / 'content'}, then import again.") from exc
    return done


def _unpack(bundle: zipfile.ZipFile, workspace: Path, repo: Path, done: Imported) -> None:
    """Write out each file: the workspace's replace a fresh `cm init`'s starter files, while a
    personal file that already exists is left as it is."""
    for entry in bundle.infolist():
        if entry.is_dir() or entry.filename == MANIFEST:
            continue
        section, _, rest = entry.filename.partition("/")
        if section == WORKSPACE:
            target = workspace / rest
        else:
            target = repo / rest
            if target.exists():
                done.kept_existing.append(rest)
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with bundle.open(entry) as source, target.open("wb") as out:
            shutil.copyfileobj(source, out)
        done.files += 1


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
