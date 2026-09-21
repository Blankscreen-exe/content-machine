"""Reading and writing drafts: staying inside the folder, and not losing work."""
from __future__ import annotations

import pytest

from cm import files
from cm.models import PieceType


def test_resolve_stays_inside_the_folder(tmp_path):
    (tmp_path / "blog.md").write_text("fine", encoding="utf-8")
    assert files.resolve(tmp_path, "blog.md").parent == tmp_path

    for attempt in ("../secrets.md", "sub/blog.md", "..\\secrets.md", "/etc/passwd"):
        with pytest.raises(files.UnsafePath):
            files.resolve(tmp_path, attempt)


def test_missing_file_reads_as_empty(tmp_path):
    text, fingerprint = files.read(tmp_path, "blog.md")
    assert text == ""
    assert fingerprint == files.digest("")


def test_write_then_read_round_trip(tmp_path):
    _, fingerprint = files.read(tmp_path, "blog.md")
    saved = files.write(tmp_path, "blog.md", "first draft", expected=fingerprint)

    text, current = files.read(tmp_path, "blog.md")
    assert text == "first draft"
    assert current == saved


def test_a_change_on_disk_blocks_the_save(tmp_path):
    """A terminal session writing to the same file must not be silently overwritten."""
    _, fingerprint = files.read(tmp_path, "blog.md")
    files.write(tmp_path, "blog.md", "mine", expected=fingerprint)

    (tmp_path / "blog.md").write_text("written by a session", encoding="utf-8")

    with pytest.raises(files.Conflict) as raised:
        files.write(tmp_path, "blog.md", "mine again", expected=fingerprint)

    assert raised.value.current_text == "written by a session"
    assert (tmp_path / "blog.md").read_text(encoding="utf-8") == "written by a session"


def test_force_overwrites_deliberately(tmp_path):
    _, fingerprint = files.read(tmp_path, "blog.md")
    (tmp_path / "blog.md").write_text("theirs", encoding="utf-8")

    files.write(tmp_path, "blog.md", "mine", expected=fingerprint, force=True)
    assert (tmp_path / "blog.md").read_text(encoding="utf-8") == "mine"


def test_main_file_first_generated_last(tmp_path):
    for name in ("brief.md", "spec.md", "blog.md", "props.md"):
        (tmp_path / name).write_text("", encoding="utf-8")

    assert files.list_drafts(tmp_path, "blog.md") == ["blog.md", "props.md", "spec.md", "brief.md"]


def test_the_main_file_is_listed_before_it_exists(tmp_path):
    assert files.list_drafts(tmp_path, "blog.md") == ["blog.md"]


def test_every_piece_type_has_a_main_file():
    assert set(files.MAIN_FILE) == set(PieceType)


def test_images_are_listed_from_assets(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "meme.png").write_bytes(b"")
    (tmp_path / "assets" / "notes.txt").write_text("", encoding="utf-8")

    assert files.images(tmp_path) == ["meme.png"]
