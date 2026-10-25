"""The due dates a cadence gives: the rule followed, taken dates never offered twice."""
from __future__ import annotations

from datetime import date

import pytest

from cm.cadence import BadRule, Rule, from_form, next_slots
from cm.models import CadenceRule

FRIDAY = date(2026, 10, 30)


def weekdays() -> Rule:
    return from_form(CadenceRule.weekdays)


def every(days: int | None) -> Rule:
    return from_form(CadenceRule.every_n_days, every_days=days)


def weekly(day: int | None) -> Rule:
    return from_form(CadenceRule.weekly, weekday=day)


def test_weekdays_step_over_the_weekend():
    assert next_slots(weekdays(), [], 3, FRIDAY) == [date(2026, 10, 30), date(2026, 11, 2), date(2026, 11, 3)]


def test_a_taken_date_is_never_offered_again():
    assert next_slots(weekdays(), [date(2026, 11, 2)], 2, FRIDAY) == [date(2026, 10, 30), date(2026, 11, 3)]


def test_every_n_days_keeps_its_distance_from_pieces_already_due():
    # a blog due on the 1st and the 7th: the 4th is 3 days from both, so the gap is filled
    taken = [date(2026, 11, 1), date(2026, 11, 7)]
    assert next_slots(every(3), taken, 3, date(2026, 10, 30)) == [
        date(2026, 11, 4), date(2026, 11, 10), date(2026, 11, 13)]


def test_every_n_days_counts_from_a_piece_due_before_the_start():
    assert next_slots(every(3), [date(2026, 10, 29)], 1, FRIDAY) == [date(2026, 11, 1)]


def test_the_slots_cross_a_month_and_a_year():
    assert next_slots(every(4), [], 3, date(2026, 12, 27)) == [
        date(2026, 12, 27), date(2026, 12, 31), date(2027, 1, 4)]


def test_weekly_falls_on_its_day():
    assert next_slots(weekly(4), [FRIDAY], 2, date(2026, 10, 26)) == [date(2026, 11, 6), date(2026, 11, 13)]


@pytest.mark.parametrize("make, problem", [
    (lambda: every(None), "Every how many days"),
    (lambda: every(0), "Every how many days"),
    (lambda: weekly(None), "which day"),
    (lambda: weekly(7), "which day"),
])
def test_a_rule_missing_its_number_is_refused(make, problem):
    with pytest.raises(BadRule, match=problem):
        make()


def test_a_rule_keeps_only_the_number_it_uses():
    assert from_form(CadenceRule.weekly, every_days=3, weekday=4) == Rule(CadenceRule.weekly, weekday=4)


def test_each_rule_says_what_it_is():
    assert [each.describe() for each in (weekdays(), every(1), every(3), weekly(4))] == [
        "every weekday", "every day", "every 3 days", "every Friday"]
