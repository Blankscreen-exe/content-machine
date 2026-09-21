"""Database tables.

An idea is the unit of thinking. A piece is a single thing that gets published — a blog
post, a LinkedIn post, a carousel — and one idea can produce several. Stages belong to
pieces, because a piece is what actually moves.

Piece types, platforms and modes are lists you manage from the app. Idea statuses, piece
stages and priorities stay in code, because the app's own behaviour depends on them.

No `from __future__ import annotations` here: SQLModel reads the relationship types at
class creation, and postponed annotations would hide them from it.
"""
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint


def now() -> datetime:
    return datetime.now(timezone.utc)


class IdeaStatus(str, Enum):
    pool = "pool"
    promoted = "promoted"
    parked = "parked"
    dropped = "dropped"


# Priority is stored as a number so lists sort by it; people see the name.
PRIORITIES: dict[int, str] = {1: "high", 2: "normal", 3: "low"}


class Stage(str, Enum):
    not_started = "not started"
    draft = "draft"
    wip = "wip"
    ready = "ready"
    published = "published"


class Brand(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)      # names the brand's folders; fixed at creation
    name: str
    active: bool = True
    # What a session needs to write as this brand. Handed over in brief.md, so the database
    # is the only copy.
    voice: str = ""
    profile: str = ""                               # identity and visual constants
    created_at: datetime = Field(default_factory=now)


class PieceType(SQLModel, table=True):
    """blog, linkedin post, carousel... shared by every brand."""

    __tablename__ = "piece_type"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    # The draft a piece of this type opens on and creates on its first save.
    main_file: str = "draft.md"
    # The most characters it should run to once pasted (a platform's limit); None for no limit.
    char_limit: int | None = None
    active: bool = True


class Platform(SQLModel, table=True):
    """Where pieces get published, so each one is always spelled the same way."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    active: bool = True


class Mode(SQLModel, table=True):
    """A stance a brand writes in. The description goes into the brief of every piece whose
    idea uses it, so a session knows what the mode means without looking anything up."""

    __table_args__ = (UniqueConstraint("brand_id", "name"),)

    id: int | None = Field(default=None, primary_key=True)
    brand_id: int = Field(foreign_key="brand.id", index=True)
    name: str
    description: str = ""
    active: bool = True


class Idea(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    brand_id: int = Field(foreign_key="brand.id", index=True)
    title: str
    angle: str = ""
    talking_points: str = ""
    mode_id: int | None = Field(default=None, foreign_key="mode.id", index=True)
    notes: str = ""
    source: str = ""
    status: IdeaStatus = Field(default=IdeaStatus.pool, index=True)
    priority: int = 2
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    mode: Optional["Mode"] = Relationship()


class Piece(SQLModel, table=True):
    """One thing that gets published. An idea can produce several; each moves on its own."""

    id: int | None = Field(default=None, primary_key=True)
    brand_id: int = Field(foreign_key="brand.id", index=True)
    idea_id: int | None = Field(default=None, foreign_key="idea.id", index=True)
    # The piece this one was made from, such as the blog post a LinkedIn post repackages.
    source_piece_id: int | None = Field(default=None, foreign_key="piece.id", index=True)
    type_id: int = Field(foreign_key="piece_type.id", index=True)
    title: str
    slug: str = ""          # fixed at creation: renaming a piece must not move its folder
    stage: Stage = Field(default=Stage.not_started, index=True)
    due_on: date | None = Field(default=None, index=True)
    notes: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    type: "PieceType" = Relationship()


class Publication(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    piece_id: int = Field(foreign_key="piece.id", index=True)
    platform_id: int = Field(foreign_key="platform.id", index=True)
    url: str = ""
    posted_at: datetime = Field(default_factory=now)
    notes: str = ""

    platform: "Platform" = Relationship()


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
