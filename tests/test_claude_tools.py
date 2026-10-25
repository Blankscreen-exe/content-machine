"""What a Claude session may do: refused where it is yours, inside one brand, and recorded as Claude's."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import Session, select

from cm import cadence, crud
from cm.claude_tools import Refused, Tools
from cm.models import Actor, CadenceRule, Event, IdeaStatus, Stage
from cm.settings import get_settings
from helpers import type_id


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture(name="tools")
def tools_fixture(session: Session, brand) -> Tools:
    return Tools(session.get_bind(), brand.slug)


@pytest.fixture(name="other")
def other_brand_fixture(session: Session):
    """A second brand in the same workspace, which a session for the first must never reach."""
    other = crud.create_brand(session, "acme-co", "Acme Co")
    idea = crud.create_idea(session, brand_id=other.id, title="Acme's idea")
    piece = crud.create_piece(session, brand_id=other.id, type_id=type_id(session, "blog"),
                              title="Acme's piece", idea_id=idea.id)
    return {"brand": other, "idea": idea, "piece": piece}


def _blog(tools: Tools, title: str = "Legacy systems") -> dict:
    return tools.create_piece("blog", title)


# --- what stays yours -------------------------------------------------------------------------

@pytest.mark.parametrize("stage", [Stage.ready, Stage.published, Stage.not_started])
def test_claude_cannot_move_a_piece_past_wip_or_back_to_the_start(tools, stage):
    piece = _blog(tools)
    with pytest.raises(Refused, match="can be moved to draft or wip"):
        tools.set_stage(piece["id"], stage)


def test_a_piece_you_have_moved_on_stays_where_you_put_it(tools, session):
    piece = _blog(tools)
    crud.update_piece(session, crud.get_piece(session, piece["id"]), stage=Stage.ready)
    with pytest.raises(Refused, match="is ready, past where you can move it"):
        tools.set_stage(piece["id"], Stage.draft)


@pytest.mark.parametrize("status", [IdeaStatus.parked, IdeaStatus.dropped])
def test_parking_or_dropping_an_idea_is_yours(tools, status):
    idea = tools.create_idea("Automation before AI")
    with pytest.raises(Refused, match="mine to decide"):
        tools.update_idea(idea["id"], status=status)


def test_there_is_no_tool_to_publish_delete_or_change_the_brand(tools):
    names = {tool.__name__ for tool in tools.all()} | {tools.still.__name__}
    for forbidden in ("publish", "delete", "ready", "voice", "profile", "setting", "platform"):
        assert not any(forbidden in name for name in names), forbidden


# --- one brand only ---------------------------------------------------------------------------

def test_another_brands_work_is_not_found(tools, other):
    with pytest.raises(Refused, match=f"There is no piece {other['piece'].id} in personal"):
        tools.get_piece(other["piece"].id)
    with pytest.raises(Refused, match=f"There is no idea {other['idea'].id} in personal"):
        tools.get_idea(other["idea"].id)
    with pytest.raises(Refused, match="There is no piece"):
        tools.set_stage(other["piece"].id, Stage.draft)
    assert tools.list_pieces() == [] and tools.list_ideas() == []


def test_new_work_cannot_be_hung_on_another_brands_idea_or_piece(tools, other):
    with pytest.raises(Refused, match="There is no idea"):
        tools.create_piece("blog", "Borrowed", idea_id=other["idea"].id)
    with pytest.raises(Refused, match="There is no piece"):
        tools.create_piece("linkedin post", "Borrowed", source_piece_id=other["piece"].id)


def test_another_brands_mode_is_not_offered(tools, session, other):
    from cm import choices
    from cm.models import Mode
    choices.create(session, Mode, "advisor", brand_id=other["brand"].id)
    with pytest.raises(Refused, match="personal has no mode called 'advisor'"):
        tools.create_idea("Borrowed stance", mode="advisor")


def test_a_brand_that_does_not_exist_is_refused_before_anything_starts(session):
    with pytest.raises(Refused, match="no brand with the slug 'nobody'"):
        Tools(session.get_bind(), "nobody")


# --- what Claude does is recorded as Claude's -------------------------------------------------

def test_every_change_claude_makes_is_recorded_as_claudes(tools, session):
    idea = tools.create_idea("Cheap decisions compound", priority="high")
    piece = tools.create_piece("blog", "Cheap decisions compound", idea_id=idea["id"])
    tools.update_piece(piece["id"], title="Cheap decisions compound, later")
    tools.set_stage(piece["id"], Stage.draft)
    tools.add_note(piece["id"], "First draft written")
    tools.update_idea(idea["id"], status=IdeaStatus.promoted)

    events = session.exec(select(Event)).all()
    assert [(e.entity, e.to_state) for e in events] == [
        ("idea", "pool"), ("piece", "not started"), ("piece", "edited"), ("piece", "draft"),
        ("piece", "edited"), ("idea", "promoted")]
    assert {e.actor for e in events} == {Actor.claude}


def test_a_new_piece_comes_with_its_folder_and_brief(tools, workspace_dir):
    piece = tools.create_piece("blog", "Legacy systems", due_on=date(2026, 11, 2))
    folder = Path(piece["folder"])
    assert folder.parent == workspace_dir / "content" / "personal" and piece["due_on"] == "2026-11-02"
    assert "# Legacy systems" in (folder / "brief.md").read_text(encoding="utf-8")


def test_notes_are_added_to_not_replaced(tools):
    piece = _blog(tools)
    tools.add_note(piece["id"], "Outline agreed")
    assert tools.add_note(piece["id"], "First draft written")["notes"] == "Outline agreed\nFirst draft written"


# --- video ------------------------------------------------------------------------------------

def test_the_example_kit_is_copied_once(tools, workspace_dir):
    example = workspace_dir / "video" / "example-kit"
    (example / "fonts").mkdir(parents=True)
    (example / "index.ts").write_text("export {};", encoding="utf-8")
    (example / "fonts" / "inter.woff2").write_bytes(b"\x00\x01binary")

    kit = tools.start_kit()["kit"]
    assert (workspace_dir / "resources" / "personal" / "kit" / "fonts" / "inter.woff2").read_bytes() == b"\x00\x01binary"
    with pytest.raises(Refused, match=re.escape(f"already has a kit, at {kit}")):
        tools.start_kit()


def test_a_still_needs_a_draft_render_first(tools):
    piece = _blog(tools)
    with pytest.raises(Refused, match="no draft render yet. Run render_draft first"):
        tools.still(piece["id"], 1.5)


# --- due dates --------------------------------------------------------------------------------

def test_a_session_gets_the_next_free_dates_by_the_brands_cadence(tools, session, brand):
    crud.set_cadence(session, brand.id, type_id(session, "blog"), cadence.from_form(CadenceRule.weekly, weekday=4))

    assert tools.next_slots("blog", 2, date(2026, 10, 26)) == ["2026-10-30", "2026-11-06"]


def test_a_type_with_no_cadence_is_refused_with_where_to_set_one(tools):
    with pytest.raises(Refused, match="no cadence for blog"):
        tools.next_slots("blog", 1)


def test_dates_are_asked_for_a_sensible_number_at_a_time(tools):
    with pytest.raises(Refused, match="1 to 100 dates"):
        tools.next_slots("blog", 0)
