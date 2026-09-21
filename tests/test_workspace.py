"""Piece folders and the brief handed to a terminal session."""
from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import Session

from cm import crud, workspace
from cm.settings import get_settings
from cm.text import slugify
from helpers import mode_id, type_id


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    """Point the workspace at a temporary folder for every test in this file."""
    settings = get_settings()
    monkeypatch.setattr(settings, "workspace", tmp_path)
    return tmp_path


@pytest.mark.parametrize("title, expected", [
    ("The cheapest technical decision", "the-cheapest-technical-decision"),
    ("Automation pays before AI does!", "automation-pays-before-ai-does"),
    ("  Spaces   and --- dashes  ", "spaces-and-dashes"),
    ("?!?", "untitled"),
])
def test_slugify(title, expected):
    assert slugify(title) == expected


def test_long_titles_are_cut_on_a_word_boundary():
    slug = slugify("why the system nobody owns is the one that breaks first on a friday night")
    assert len(slug) <= 50
    assert not slug.endswith("-")


def test_folder_uses_brand_date_slug_and_type(session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"),
                              title="The cheapest technical decision")
    folder = workspace.piece_folder(session, piece)

    assert folder.parent.name == "personal"
    assert folder.name == f"{date.today().isoformat()}-the-cheapest-technical-decision-blog"


def test_pieces_from_one_idea_never_share_a_folder(session: Session, brand):
    """'Make a piece' copies the idea's title, so same-titled pieces are the normal case."""
    idea = crud.create_idea(session, brand_id=brand.id, title="Cheap decisions compound")
    made = [crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, kind), title=idea.title,
                              idea_id=idea.id)
            for kind in ("blog", "linkedin post", "carousel", "blog")]

    folders = {workspace.piece_folder(session, piece) for piece in made}
    assert len(folders) == len(made)
    assert made[-1].slug.endswith("-blog-2")          # a second blog gets a counter


def test_renaming_a_piece_keeps_its_folder(session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="First name")
    before = workspace.piece_folder(session, piece)

    crud.update_piece(session, piece, title="A completely different name")
    assert workspace.piece_folder(session, piece) == before


def test_brief_holds_what_a_session_needs(session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Cheap decisions compound",
                            angle="cheap now, expensive later",
                            talking_points="cheap code; cheap hosting",
                            mode_id=mode_id(session, brand.id, "advisor", "calm and diagnostic"))
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "carousel"),
                              title="Cheap decisions compound", idea_id=idea.id,
                              due_on=date(2026, 10, 1))

    brief = workspace.write_brief(session, piece)
    text = brief.read_text(encoding="utf-8")

    assert brief.name == "brief.md"
    assert "carousel" in text
    assert "2026-10-01" in text
    assert "cheap now, expensive later" in text
    assert "cheap code; cheap hosting" in text
    assert "### Mode: advisor" in text and "calm and diagnostic" in text
    assert f"cm stage {piece.id}" in text          # how to report back
    assert (brief.parent / "assets").is_dir()      # images have somewhere to go


def test_brief_lists_sibling_pieces(session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="One idea, many pieces")
    blog = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title=idea.title,
                             idea_id=idea.id)
    crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "linkedin post"), title=idea.title,
                      idea_id=idea.id, stage="draft")

    text = workspace.write_brief(session, blog).read_text(encoding="utf-8")
    assert "Other pieces from this idea" in text
    assert "linkedin post — draft" in text


def test_brief_says_when_a_brand_has_no_voice(session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="No voice yet")
    assert "No voice written" in workspace.write_brief(session, piece).read_text(encoding="utf-8")


def test_brief_carries_the_voice_and_profile_marked_off_from_its_own_sections(session: Session,
                                                                             brand):
    crud.update_brand(session, brand, voice="# Voice\n\n## Always\n- plain words",
                      profile="# Brand\n\n| Accent | [#2f6fdb] |")
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"),
                              title="Voiced")

    text = workspace.write_brief(session, piece).read_text(encoding="utf-8")

    voice = text.index("----- start of the voice"), text.index("----- end of the voice -----")
    assert text.index("## Always") in range(*voice)            # the voice's heading stays inside it
    assert "----- start of the brand profile" in text and "[#2f6fdb]" in text
    assert text.index("## This piece") < voice[0]              # the brief's own sections come first
