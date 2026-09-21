"""What is due: pieces past their date, and pieces coming up soon.

The app raises its own reminders by showing these where you already look — a count on the
Calendar tab and a list above the month — rather than by running anything in the background.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session

from . import crud
from .models import Piece


@dataclass(frozen=True)
class Due:
    overdue: list[Piece]
    soon: list[Piece]
    window_days: int

    @property
    def count(self) -> int:
        return len(self.overdue) + len(self.soon)


def window_days(session: Session) -> int:
    """How far ahead "due soon" looks, from Settings."""
    return int(crud.get_settings_map(session)["due_soon_days"])


def due(session: Session, today: date, brand_id: int | None = None) -> Due:
    """Unpublished pieces due before today, and those due from today to the end of the window."""
    days = window_days(session)
    pieces = crud.due_pieces(session, today + timedelta(days=days), brand_id)
    return Due(overdue=[p for p in pieces if p.due_on < today],
               soon=[p for p in pieces if p.due_on >= today],
               window_days=days)
