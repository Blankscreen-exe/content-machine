"""Stored times are UTC; people see their own calendar date."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud
from cm.dates import local_date


def test_a_naive_stored_time_is_read_as_utc():
    """SQLite returns stored times without a timezone; reading them as local would shift the date."""
    stored = datetime(2026, 9, 20, 23, 30)                     # as it comes back from SQLite
    as_utc = datetime(2026, 9, 20, 23, 30, tzinfo=timezone.utc)
    assert local_date(stored) == as_utc.astimezone().date()


def test_an_aware_time_is_converted_not_relabelled():
    moment = datetime(2026, 9, 20, 23, 30, tzinfo=timezone.utc)
    assert local_date(moment) == moment.astimezone().date()


def test_the_ideas_list_shows_the_local_date(client: TestClient, session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Dated idea")
    session.refresh(idea)                                      # read back the way the page does

    assert f">{local_date(idea.updated_at).isoformat()}<" in client.get("/ideas").text


def test_a_recorded_date_reads_back_as_that_date():
    """A post recorded "on 20 September" must show 20 September, whatever the timezone."""
    from datetime import date

    from cm.dates import moment_on

    day = date(2026, 3, 29)                                    # a clock-change weekend in Europe
    assert local_date(moment_on(day).replace(tzinfo=None)) == day   # stored naive, as SQLite does
