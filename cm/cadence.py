"""How often a brand publishes a piece type, and the due dates that gives.

Three rules, few enough that each is plain from its name:

- weekdays: Monday to Friday.
- every N days: at least N days from every other piece of the type, so a gap left earlier
  is filled rather than every new piece going after the last one.
- weekly: on one day of the week.

A date already taken by a piece of the type, for the brand, is never offered again: one
piece of a type a day. Nothing here touches the database, so the rules can be tested on
plain dates.
"""
from __future__ import annotations

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from .models import Cadence, CadenceRule

WEEKDAYS = list(calendar.day_name)          # Monday first, as date.weekday() counts
LONGEST_GAP = 365


class BadRule(ValueError):
    """A cadence that cannot be followed; the message says what is missing."""


@dataclass(frozen=True)
class Rule:
    kind: CadenceRule
    every_days: int | None = None
    weekday: int | None = None

    def __post_init__(self) -> None:
        if self.kind is CadenceRule.every_n_days and not (
                self.every_days and 1 <= self.every_days <= LONGEST_GAP):
            raise BadRule(f"Every how many days? Give a number from 1 to {LONGEST_GAP}.")
        if self.kind is CadenceRule.weekly and self.weekday not in range(7):
            raise BadRule("Weekly on which day?")

    @classmethod
    def of(cls, cadence: Cadence) -> Rule:
        return cls(cadence.rule, cadence.every_days, cadence.weekday)

    def describe(self) -> str:
        """'every weekday', 'every 3 days', 'every Friday'."""
        if self.kind is CadenceRule.weekdays:
            return "every weekday"
        if self.kind is CadenceRule.every_n_days:
            return "every day" if self.every_days == 1 else f"every {self.every_days} days"
        return f"every {WEEKDAYS[self.weekday]}"

    def allows(self, day: date, used: set[date]) -> bool:
        """Whether `day` is a slot, given the dates already used."""
        if day in used:
            return False
        if self.kind is CadenceRule.weekdays:
            return day.weekday() < 5
        if self.kind is CadenceRule.weekly:
            return day.weekday() == self.weekday
        return all(abs((day - other).days) >= self.every_days for other in used)


def from_form(kind: CadenceRule, every_days: int | None = None, weekday: int | None = None) -> Rule:
    """A rule from what a form sends: all three fields, of which the kind uses one at most.
    The others are dropped, so a stored cadence never carries a number it ignores."""
    return Rule(kind, every_days if kind is CadenceRule.every_n_days else None,
                weekday if kind is CadenceRule.weekly else None)


def next_slots(rule: Rule, taken: Iterable[date], count: int, start: date) -> list[date]:
    """The first `count` dates from `start` on that `rule` allows, around the `taken` ones.

    Each slot chosen counts as taken for the next, so asking for ten gives ten dates that
    keep the rule among themselves too. Every rule has a slot within its longest gap past the
    last taken date, so this always ends.
    """
    used = set(taken)
    slots: list[date] = []
    day = start
    while len(slots) < count:
        if rule.allows(day, used):
            slots.append(day)
            used.add(day)
        day += timedelta(days=1)
    return slots
