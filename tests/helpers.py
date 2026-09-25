"""Small lookups the tests share: the managed lists are rows now, so tests name them."""
from __future__ import annotations

from sqlmodel import Session

from cm import choices
from cm.models import Mode, PieceType, Platform

# What the migration seeds a real database with; conftest seeds the test database the same way.
# (name, main file, character limit, video)
STANDARD_TYPES = [
    ("blog", "blog.md", None, False),
    ("linkedin post", "linkedin.md", 3000, False),
    ("x post", "x.md", 280, False),
    ("infographic", "spec.md", None, False),
    ("carousel", "spec.md", None, False),
    ("quote", "quotes.md", None, False),
    ("other", "draft.md", None, False),
    ("youtube short", "frames.md", None, True),
]


def type_id(session: Session, name: str) -> int:
    return choices.by_name(session, PieceType, name).id


def platform_id(session: Session, name: str) -> int:
    """The platform's id, adding it first if the test has not."""
    found = choices.by_name(session, Platform, name) or choices.create(session, Platform, name)
    return found.id


def mode_id(session: Session, brand_id: int, name: str, description: str = "") -> int:
    found = (choices.by_name(session, Mode, name, brand_id)
             or choices.create(session, Mode, name, brand_id=brand_id, description=description))
    return found.id
