"""Reminders: what is overdue or due soon shows on the Pieces tab and above the list."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, schedule
from cm.models import Stage

TODAY = date(2026, 9, 21)


@pytest.fixture(name="dated")
def dated_fixture(session: Session, brand):
    """One piece each: overdue, due today, inside the window, beyond it, and published."""
    def piece(title, days, stage=Stage.draft):
        return crud.create_piece(session, brand_id=brand.id, type="blog", title=title,
                                 due_on=TODAY + timedelta(days=days), stage=stage)
    return {
        "overdue": piece("Overdue", -2),
        "today": piece("Today", 0),
        "soon": piece("Soon", 7),
        "later": piece("Later", 8),
        "done": piece("Done", -5, Stage.published),
    }


def _titles(pieces):
    return [p.title for p in pieces]


def test_overdue_and_soon_are_split_and_published_work_is_left_out(session: Session, dated):
    due = schedule.due(session, TODAY)
    assert _titles(due.overdue) == ["Overdue"]
    assert _titles(due.soon) == ["Today", "Soon"]      # the window's last day counts
    assert due.count == 3


def test_the_window_comes_from_settings(session: Session, dated):
    crud.set_setting(session, "due_soon_days", "0")
    assert _titles(schedule.due(session, TODAY).soon) == ["Today"]


def test_the_pieces_page_shows_the_panel_and_the_tab_count(client: TestClient, session: Session,
                                                          brand):
    crud.create_piece(session, brand_id=brand.id, type="blog", title="Late one",
                      due_on=date.today() - timedelta(days=1))
    page = client.get("/pieces").text

    assert 'id="due" class="panel due">' in page and "Late one" in page
    assert 'class="due-badge"' in page and ">1</span>" in page


def test_nothing_due_hides_both(client: TestClient, brand):
    page = client.get("/pieces").text
    assert 'id="due" class="panel due" hidden>' in page
    assert '<span id="due-badge" class="due-badge" hidden' in page


def test_publishing_from_the_list_updates_the_count(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type="blog", title="Late one",
                              due_on=date.today() - timedelta(days=1))

    response = client.post(f"/pieces/{piece.id}/stage", data={"stage": "published", "brand_id": ""})

    assert '<span id="due-badge" class="due-badge" hx-swap-oob="true" hidden' in response.text
    assert 'id="due" class="panel due" hx-swap-oob="true" hidden>' in response.text


def test_the_window_is_checked_when_set(client: TestClient, session: Session):
    for bad in ("soon", "-1", "366", "2.5"):
        response = client.post("/settings", data={"key": "due_soon_days", "value": bad})
        assert response.status_code == 400, bad
        assert "whole number of days" in response.json()["detail"]
    assert client.post("/settings", data={"key": "due_soon_days", "value": " 14 "}).status_code == 204
    assert crud.get_settings_map(session)["due_soon_days"] == "14"
