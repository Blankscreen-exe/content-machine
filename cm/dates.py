"""Turning stored times into the dates a person expects.

Times are stored in UTC. SQLite hands them back without a timezone, so they are marked as
UTC before being converted — otherwise a naive value would be read as local time and the
date could be a day off either way.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def local_date(moment: datetime) -> date:
    """The date on this machine's calendar for a stored moment."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().date()
