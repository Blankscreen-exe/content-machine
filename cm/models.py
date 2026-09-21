"""Database tables.

An idea is the unit of thinking. A piece is a single thing that gets published — a blog
post, a LinkedIn post, a carousel — and one idea can produce several. Stages belong to
pieces, because a piece is what actually moves.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class IdeaStatus(str, Enum):
    pool = "pool"
    promoted = "promoted"
    parked = "parked"
    dropped = "dropped"


class Stage(str, Enum):
    not_started = "not started"
    draft = "draft"
    wip = "wip"
    ready = "ready"
    published = "published"


class PieceType(str, Enum):
    blog = "blog"
    linkedin = "linkedin post"
    x = "x post"
    infographic = "infographic"
    carousel = "carousel"
    quote = "quote"
    other = "other"


class Brand(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    active: bool = True
    created_at: datetime = Field(default_factory=now)


class Idea(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    brand_id: int = Field(foreign_key="brand.id", index=True)
    title: str
    angle: str = ""
    talking_points: str = ""
    mode: str = ""
    notes: str = ""
    source: str = ""
    status: IdeaStatus = Field(default=IdeaStatus.pool, index=True)
    priority: int = 2
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Piece(SQLModel, table=True):
    """One thing that gets published. An idea can produce several; each moves on its own."""

    id: int | None = Field(default=None, primary_key=True)
    brand_id: int = Field(foreign_key="brand.id", index=True)
    idea_id: int | None = Field(default=None, foreign_key="idea.id", index=True)
    type: PieceType
    title: str
    slug: str = ""          # fixed at creation: renaming a piece must not move its folder
    stage: Stage = Field(default=Stage.not_started, index=True)
    due_on: date | None = Field(default=None, index=True)
    notes: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Publication(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    piece_id: int = Field(foreign_key="piece.id", index=True)
    platform: str
    url: str = ""
    posted_at: datetime = Field(default_factory=now)
    notes: str = ""


class Event(SQLModel, table=True):
    """Audit trail: when a thing changed state, and to what."""

    id: int | None = Field(default=None, primary_key=True)
    entity: str = Field(index=True)
    entity_id: int = Field(index=True)
    from_state: str = ""
    to_state: str = ""
    at: datetime = Field(default_factory=now)
    note: str = ""


class Setting(SQLModel, table=True):
    """Small key/value store for UI preferences, so they follow you between devices."""

    key: str = Field(primary_key=True)
    value: str
