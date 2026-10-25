"""A piece's history as its page shows it: when, who, and what happened, in words."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session

from . import crud
from .models import Actor, Event

WHO = {Actor.me: "You", Actor.claude: "Claude"}


@dataclass(frozen=True)
class Entry:
    at: datetime
    who: str
    what: str


def of_piece(session: Session, piece_id: int) -> list[Entry]:
    """Newest first."""
    return [Entry(event.at, WHO[event.actor], describe(event))
            for event in crud.list_events(session, "piece", piece_id)]


def describe(event: Event) -> str:
    """'draft → wip', 'edited: title, due_on', 'created (blog)'."""
    if event.to_state == crud.EDITED:
        return f"edited: {event.note}"
    if event.from_state:
        return f"{event.from_state} → {event.to_state}"
    return event.note or event.to_state
