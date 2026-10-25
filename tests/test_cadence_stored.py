"""Cadences as stored and set: on the brand's Manage page, and the dates they give a brand."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import cadence, choices, crud
from cm.models import CadenceRule, PieceType
from helpers import type_id

FRIDAY = date(2026, 10, 30)


def _set(client: TestClient, brand, kind_id: int, **form) -> str:
    return client.post(f"/manage/brands/{brand.id}/cadence/{kind_id}", data=form).text


def test_a_cadence_set_on_the_brand_page_is_kept_and_shown(client: TestClient, session: Session, brand):
    blog = type_id(session, "blog")

    answer = _set(client, brand, blog, rule="every n days", every_days="3", weekday="2")

    assert "blog: every 3 days." in answer
    stored = crud.get_cadence(session, brand.id, blog)
    assert (stored.rule, stored.every_days, stored.weekday) == (CadenceRule.every_n_days, 3, None)
    assert "every 3 days" in client.get(f"/manage/brands/{brand.id}").text


def test_no_rhythm_takes_the_cadence_away(client: TestClient, session: Session, brand):
    blog = type_id(session, "blog")
    _set(client, brand, blog, rule="weekdays")

    assert "blog: no rhythm." in _set(client, brand, blog, rule="")
    assert crud.get_cadence(session, brand.id, blog) is None


@pytest.mark.parametrize("form, problem", [
    ({"rule": "every n days", "every_days": ""}, "Every how many days"),
    ({"rule": "every n days", "every_days": "three"}, "is not a whole number"),
    ({"rule": "weekly", "weekday": ""}, "Weekly on which day"),
])
def test_a_cadence_missing_its_number_is_refused_and_nothing_changes(client: TestClient, session: Session,
                                                                     brand, form, problem):
    blog = type_id(session, "blog")
    _set(client, brand, blog, rule="weekdays")

    assert problem in _set(client, brand, blog, **form)
    assert crud.get_cadence(session, brand.id, blog).rule is CadenceRule.weekdays


def test_the_dates_skip_this_types_pieces_and_no_others(session: Session, brand):
    blog, post = type_id(session, "blog"), type_id(session, "linkedin post")
    other = crud.create_brand(session, "acme-co", "Acme Co")
    crud.set_cadence(session, brand.id, blog, cadence.from_form(CadenceRule.weekdays))
    crud.create_piece(session, brand_id=brand.id, type_id=blog, title="Taken", due_on=FRIDAY)
    crud.create_piece(session, brand_id=brand.id, type_id=post, title="Another type", due_on=date(2026, 11, 2))
    crud.create_piece(session, brand_id=other.id, type_id=blog, title="Another brand", due_on=date(2026, 11, 3))

    assert crud.next_slots(session, brand.id, blog, 2, FRIDAY) == [date(2026, 11, 2), date(2026, 11, 3)]


def test_a_type_with_no_cadence_says_where_to_set_one(session: Session, brand):
    with pytest.raises(cadence.BadRule, match="no cadence for blog.*under Manage"):
        crud.next_slots(session, brand.id, type_id(session, "blog"), 1, FRIDAY)


def test_deleting_a_piece_type_takes_its_cadences_with_it(session: Session, brand):
    meme = choices.create(session, PieceType, "meme", main_file="meme.md")
    crud.set_cadence(session, brand.id, meme.id, cadence.from_form(CadenceRule.weekly, weekday=2))

    choices.delete(session, meme)          # nothing uses it, so the delete is allowed

    assert crud.list_cadences(session, brand.id) == {}
