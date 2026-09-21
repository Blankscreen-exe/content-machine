"""A month laid out as weeks, with the pieces due on each day.

Built on the standard library's `calendar`, which already knows how months fall into
weeks; this only puts pieces on the days.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date

from .models import Piece

# Weeks start on Monday, as ISO dates and most European calendars do.
FIRST_WEEKDAY = calendar.MONDAY
WEEKDAY_NAMES = [calendar.day_abbr[(FIRST_WEEKDAY + i) % 7] for i in range(7)]


@dataclass
class Day:
    on: date
    in_month: bool            # the grid starts and ends on whole weeks, so it shows a few neighbours
    is_today: bool
    pieces: list[Piece] = field(default_factory=list)


@dataclass(frozen=True)
class Month:
    first: date               # the 1st of the month shown
    weeks: list[list[Day]]

    @property
    def title(self) -> str:
        return f"{calendar.month_name[self.first.month]} {self.first.year}"

    @property
    def previous(self) -> date:
        return shift(self.first, -1)

    @property
    def next(self) -> date:
        return shift(self.first, 1)

    @property
    def start(self) -> date:
        return self.weeks[0][0].on

    @property
    def end(self) -> date:
        return self.weeks[-1][-1].on


def shift(first: date, months: int) -> date:
    """The 1st of the month `months` away from `first`."""
    index = first.year * 12 + first.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def parse(value: str | None, today: date) -> date:
    """The 1st of the month named by `YYYY-MM`, or of this month if it is missing or malformed."""
    try:
        year, month = (int(part) for part in (value or "").split("-"))
        return date(year, month, 1)
    except ValueError:
        return today.replace(day=1)


def grid(first: date, today: date) -> Month:
    """The empty month: every day shown, whole weeks, nothing placed yet."""
    weeks = calendar.Calendar(FIRST_WEEKDAY).monthdatescalendar(first.year, first.month)
    return Month(first, [[Day(on, on.month == first.month, on == today) for on in week]
                         for week in weeks])


def place(month: Month, pieces: list[Piece]) -> Month:
    """Put each dated piece on its day. Pieces outside the grid are ignored."""
    days = {day.on: day for week in month.weeks for day in week}
    for piece in pieces:
        if piece.due_on in days:
            days[piece.due_on].pieces.append(piece)
    return month
