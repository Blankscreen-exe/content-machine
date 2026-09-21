"""The Calendar tab: a month of pieces by due date, and what is due."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, month
from cm.models import Stage
from helpers import type_id


def test_a_month_is_whole_weeks_starting_on_monday():
    grid = month.grid(date(2026, 9, 1), today=date(2026, 9, 21))

    assert grid.title == "September 2026"
    assert all(len(week) == 7 for week in grid.weeks)
    assert grid.start == date(2026, 8, 31) and grid.start.weekday() == 0
    assert grid.end == date(2026, 10, 4)
    assert [d.on for w in grid.weeks for d in w if d.is_today] == [date(2026, 9, 21)]
    assert not grid.weeks[0][0].in_month and grid.weeks[0][1].in_month


@pytest.mark.parametrize("first, months, expected", [
    (date(2026, 12, 1), 1, date(2027, 1, 1)),
    (date(2026, 1, 1), -1, date(2025, 12, 1)),
    (date(2026, 9, 1), 0, date(2026, 9, 1)),
])
def test_moving_between_months_crosses_years(first, months, expected):
    assert month.shift(first, months) == expected


@pytest.mark.parametrize("value", [None, "", "2026", "2026-13", "banana", "2026-09-01"])
def test_a_bad_month_in_the_address_shows_this_month(value):
    assert month.parse(value, today=date(2026, 9, 21)) == date(2026, 9, 1)


def test_pieces_land_on_their_due_day(session: Session, brand):
    blog = type_id(session, "blog")
    crud.create_piece(session, brand_id=brand.id, type_id=blog, title="On the 23rd", due_on=date(2026, 9, 23))
    crud.create_piece(session, brand_id=brand.id, type_id=blog, title="Next month", due_on=date(2026, 10, 2))
    crud.create_piece(session, brand_id=brand.id, type_id=blog, title="Out of view", due_on=date(2026, 11, 20))

    grid = month.grid(date(2026, 9, 1), today=date(2026, 9, 21))
    month.place(grid, crud.pieces_due_between(session, grid.start, grid.end))
    placed = {day.on: [p.title for p in day.pieces] for week in grid.weeks for day in week if day.pieces}

    assert placed == {date(2026, 9, 23): ["On the 23rd"], date(2026, 10, 2): ["Next month"]}


def test_the_calendar_page_shows_the_month_and_its_pieces(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"),
                              title="Due in the shown month", due_on=date(2026, 9, 23), stage=Stage.draft)

    page = client.get("/calendar?month=2026-09").text

    assert "<h2>September 2026</h2>" in page
    assert f'href="/pieces/{piece.id}"' in page and "status-draft" in page
    assert 'href="/calendar?month=2026-08"' in page and 'href="/calendar?month=2026-10"' in page


def test_the_brand_filter_narrows_the_month_and_keeps_it(client: TestClient, session: Session, brand):
    other = crud.create_brand(session, "acme", "Acme Co")
    blog = type_id(session, "blog")
    crud.create_piece(session, brand_id=brand.id, type_id=blog, title="Mine", due_on=date(2026, 9, 23))
    crud.create_piece(session, brand_id=other.id, type_id=blog, title="Theirs", due_on=date(2026, 9, 24))

    page = client.get(f"/calendar?month=2026-09&brand_id={other.id}").text

    assert ">Theirs</a>" in page and ">Mine</a>" not in page
    assert '<input type="hidden" name="month" value="2026-09">' in page     # changing brand stays here
    assert f'month=2026-10&amp;brand_id={other.id}' in page                 # and so do the arrows


def test_published_pieces_stay_on_the_calendar(client: TestClient, session: Session, brand):
    crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Went out",
                      due_on=date(2026, 9, 10), stage=Stage.published)
    assert ">Went out</a>" in client.get("/calendar?month=2026-09").text


def test_undated_work_is_counted_since_it_cannot_be_shown(client: TestClient, session: Session, brand):
    crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Someday")
    assert "no due date: 1 unpublished" in client.get("/calendar").text
