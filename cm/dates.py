"""Turning stored times into the dates a person expects.

Times are stored in UTC. SQLite hands them back without a timezone, so they are marked as
UTC before being converted — otherwise a naive value would be read as local time and the
date could be a day off either way.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone


def local_date(moment: datetime) -> date:
    """The date on this machine's calendar for a stored moment."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().date()


def moment_on(day: date) -> datetime:
    """A stored moment that falls on `day` on this machine's calendar.

    Used when only a date is known, such as a post recorded after the fact. Noon leaves
    twelve hours either side, so a clock change never pushes it onto a neighbouring day.
    """
    return datetime.combine(day, time(12)).astimezone().astimezone(timezone.utc)
