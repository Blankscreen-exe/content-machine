"""Small lookups the tests share: the managed lists are rows now, so tests name them."""
from __future__ import annotations

from sqlmodel import Session

from cm import choices
from cm.models import Mode, PieceType, Platform

# What the migration seeds a real database with; conftest seeds the test database the same way.
STANDARD_TYPES = [
    ("blog", "blog.md", None),
    ("linkedin post", "linkedin.md", 3000),
    ("x post", "x.md", 280),
    ("infographic", "spec.md", None),
    ("carousel", "spec.md", None),
    ("quote", "quotes.md", None),
    ("other", "draft.md", None),
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
