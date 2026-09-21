"""Database operations.

Both the web app and the CLI call these, so the rules live in one place.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from sqlmodel import Session, func, or_, select

from .choices import ChoiceError
from .models import (Brand, Event, Idea, IdeaStatus, Mode, Piece, PieceType, Publication,
                     Setting, Stage, now)
from .text import slugify

DEFAULT_SETTINGS = {"theme": "1996", "due_soon_days": "7"}


# ---------- events ----------

def record(session: Session, entity: str, entity_id: int, to_state: str,
           from_state: str = "", note: str = "") -> None:
    session.add(Event(entity=entity, entity_id=entity_id,
                      from_state=from_state, to_state=to_state, note=note))


# ---------- settings ----------

def get_settings_map(session: Session) -> dict[str, str]:
    stored = {s.key: s.value for s in session.exec(select(Setting)).all()}
    return {**DEFAULT_SETTINGS, **stored}


def set_setting(session: Session, key: str, value: str) -> None:
    setting = session.get(Setting, key)
    if setting:
        setting.value = value
    else:
        session.add(Setting(key=key, value=value))
    session.commit()


# ---------- brands ----------

def list_brands(session: Session) -> list[Brand]:
    return list(session.exec(select(Brand).order_by(Brand.active.desc(), Brand.name)).all())


def get_brand_by_slug(session: Session, slug: str) -> Brand | None:
    return session.exec(select(Brand).where(Brand.slug == slug)).first()


def brand_slug(session: Session, brand_id: int) -> str:
    brand = session.get(Brand, brand_id)
    return brand.slug if brand else "unknown-brand"


def get_brand(session: Session, brand_id: int) -> Brand | None:
    return session.get(Brand, brand_id)


def update_brand(session: Session, brand: Brand, **fields) -> Brand:
    for key, value in fields.items():
        setattr(brand, key, value)
    session.add(brand)
    session.commit()
    session.refresh(brand)
    return brand


BRAND_SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def create_brand(session: Session, slug: str, name: str | None = None, **fields) -> Brand:
    """Add a brand. The slug names its folders, so it has to be folder-safe and unique."""
    slug = slug.strip()
    if not BRAND_SLUG.fullmatch(slug):
        raise ChoiceError("A slug is lowercase letters, numbers and dashes, like acme-co.")
    if get_brand_by_slug(session, slug):
        raise ChoiceError(f"There is already a brand with the slug {slug}.")
    brand = Brand(slug=slug, name=" ".join((name or slug).split()), **fields)
    session.add(brand)
    session.commit()
    session.refresh(brand)
    return brand


# ---------- ideas ----------

def list_ideas(session: Session, brand_id: int | None = None,
               status: IdeaStatus | None = None, search: str | None = None) -> list[Idea]:
    query = select(Idea)
    if brand_id:
        query = query.where(Idea.brand_id == brand_id)
    if status:
        query = query.where(Idea.status == status)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(or_(Idea.title.like(like),
                                Idea.angle.like(like),
                                Idea.talking_points.like(like)))
    query = query.order_by(Idea.priority, Idea.updated_at.desc())
    return list(session.exec(query).all())


def get_idea(session: Session, idea_id: int) -> Idea | None:
    return session.get(Idea, idea_id)


def _check_mode(session: Session, brand_id: int, mode_id: int | None) -> None:
    """A mode belongs to one brand; an idea can only use one of its own brand's."""
    if mode_id is None:
        return
    mode = session.get(Mode, mode_id)
    if not mode or mode.brand_id != brand_id:
        raise ChoiceError("That mode belongs to another brand.")


def create_idea(session: Session, brand_id: int, **fields) -> Idea:
    _check_mode(session, brand_id, fields.get("mode_id"))
    idea = Idea(brand_id=brand_id, **fields)
    session.add(idea)
    session.commit()
    session.refresh(idea)
    record(session, "idea", idea.id, to_state=idea.status.value, note="created")
    session.commit()
    return idea


def update_idea(session: Session, idea: Idea, **fields) -> Idea:
    if "mode_id" in fields:
        _check_mode(session, idea.brand_id, fields["mode_id"])
    previous = idea.status
    for key, value in fields.items():
        setattr(idea, key, value)
    idea.updated_at = now()
    session.add(idea)
    session.commit()
    session.refresh(idea)
    if idea.status != previous:
        record(session, "idea", idea.id, to_state=idea.status.value, from_state=previous.value)
        session.commit()
    return idea


def delete_idea(session: Session, idea: Idea) -> None:
    """Delete an idea. Its pieces are real work, so they stay, as standalone pieces."""
    for piece in session.exec(select(Piece).where(Piece.idea_id == idea.id)).all():
        piece.idea_id = None
        session.add(piece)
    # Write the detachment before the delete: with no relationships declared, SQLAlchemy
    # does not know the order matters, and the foreign key would reject the reverse.
    session.flush()
    record(session, "idea", idea.id, to_state="deleted",
           from_state=idea.status.value, note=idea.title)
    session.delete(idea)
    session.commit()


# ---------- pieces ----------

def list_pieces(session: Session, brand_id: int | None = None, stage: Stage | None = None,
                type_id: int | None = None, idea_id: int | None = None) -> list[Piece]:
    query = select(Piece)
    if brand_id:
        query = query.where(Piece.brand_id == brand_id)
    if stage:
        query = query.where(Piece.stage == stage)
    if type_id:
        query = query.where(Piece.type_id == type_id)
    if idea_id:
        query = query.where(Piece.idea_id == idea_id)
    # Dated work first, oldest due date at the top; undated work after it.
    query = query.order_by(Piece.due_on.is_(None), Piece.due_on, Piece.updated_at.desc())
    return list(session.exec(query).all())


def get_piece(session: Session, piece_id: int) -> Piece | None:
    return session.get(Piece, piece_id)


def unique_slug(session: Session, brand_id: int, title: str, type_name: str) -> str:
    """A slug no other piece of this brand has.

    The slug names the piece's folder, and pieces made from one idea share its title, so
    the type goes into the slug and a counter settles any remaining clash. Without this,
    two pieces could write into the same folder and overwrite each other's files.
    """
    base = f"{slugify(title)}-{slugify(type_name)}"
    taken = set(session.exec(select(Piece.slug).where(Piece.brand_id == brand_id)).all())
    slug, counter = base, 2
    while slug in taken:
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def create_piece(session: Session, brand_id: int, type_id: int, title: str, **fields) -> Piece:
    piece_type = session.get(PieceType, type_id)
    if not piece_type:
        raise ChoiceError("That piece type does not exist.")
    fields["slug"] = unique_slug(session, brand_id, title, piece_type.name)
    piece = Piece(brand_id=brand_id, type_id=type_id, title=title.strip(), **fields)
    session.add(piece)
    session.commit()
    session.refresh(piece)
    record(session, "piece", piece.id, to_state=piece.stage.value, note=f"created ({piece_type.name})")
    session.commit()
    return piece


def update_piece(session: Session, piece: Piece, **fields) -> Piece:
    previous = piece.stage
    for key, value in fields.items():
        setattr(piece, key, value)
    piece.updated_at = now()
    session.add(piece)
    session.commit()
    session.refresh(piece)
    if piece.stage != previous:
        record(session, "piece", piece.id, to_state=piece.stage.value, from_state=previous.value)
        session.commit()
    return piece


def delete_piece(session: Session, piece: Piece) -> None:
    """Delete a piece and the record of where it was published, which only describes it.

    Files are not touched here; `workspace.delete_piece` moves the folder to the trash
    and then calls this.
    """
    for publication in session.exec(select(Publication).where(Publication.piece_id == piece.id)).all():
        session.delete(publication)
    # Pieces made from this one are their own work now; they only lose the pointer back.
    for derived in session.exec(select(Piece).where(Piece.source_piece_id == piece.id)).all():
        derived.source_piece_id = None
        session.add(derived)
    session.flush()   # before the delete, for the same reason as in delete_idea
    record(session, "piece", piece.id, to_state="deleted",
           from_state=piece.stage.value, note=piece.title)
    session.delete(piece)
    session.commit()


def derive_piece(session: Session, source: Piece, type_id: int) -> Piece:
    """A new piece of another type made from `source`: same brand, idea and title, and a
    pointer back so its brief can say which draft to work from."""
    return create_piece(session, brand_id=source.brand_id, type_id=type_id, title=source.title,
                        idea_id=source.idea_id, source_piece_id=source.id)


def record_publication(session: Session, piece: Piece, platform_id: int, url: str = "",
                       notes: str = "", posted_at: datetime | None = None) -> Publication:
    """Record where a piece went out, and move it to published.

    `posted_at` is for recording a post after the fact; left out, it is now.
    """
    publication = Publication(piece_id=piece.id, platform_id=platform_id, url=url.strip(),
                              notes=notes, posted_at=posted_at or now())
    session.add(publication)
    session.commit()
    session.refresh(publication)
    update_piece(session, piece, stage=Stage.published)
    return publication


def get_publication(session: Session, publication_id: int) -> Publication | None:
    return session.get(Publication, publication_id)


def delete_publication(session: Session, publication: Publication) -> None:
    """Remove a record made by mistake. The piece keeps its stage; change that yourself."""
    session.delete(publication)
    session.commit()


def list_publications(session: Session, piece_id: int) -> list[Publication]:
    return list(session.exec(
        select(Publication).where(Publication.piece_id == piece_id).order_by(Publication.posted_at)
    ).all())


def pieces_due_between(session: Session, first: date, last: date,
                       brand_id: int | None = None) -> list[Piece]:
    """Every piece due from `first` to `last`, published or not: a calendar shows both."""
    query = select(Piece).where(Piece.due_on >= first, Piece.due_on <= last)
    if brand_id:
        query = query.where(Piece.brand_id == brand_id)
    return list(session.exec(query.order_by(Piece.due_on, Piece.title)).all())


def undated_count(session: Session, brand_id: int | None = None) -> int:
    """Unpublished pieces with no due date, which a calendar cannot show."""
    query = select(func.count()).select_from(Piece).where(Piece.due_on.is_(None),
                                                          Piece.stage != Stage.published)
    if brand_id:
        query = query.where(Piece.brand_id == brand_id)
    return session.exec(query).one()


IN_PROGRESS = (Stage.draft, Stage.wip, Stage.ready)


def pieces_in_progress(session: Session, brand_id: int | None = None, limit: int = 10) -> list[Piece]:
    """Started and not yet out: soonest due first, undated after, most recently touched first."""
    query = select(Piece).where(Piece.stage.in_(IN_PROGRESS))
    if brand_id:
        query = query.where(Piece.brand_id == brand_id)
    query = query.order_by(Piece.due_on.is_(None), Piece.due_on, Piece.updated_at.desc())
    return list(session.exec(query.limit(limit)).all())


def top_pool_ideas(session: Session, brand_id: int | None = None, limit: int = 5) -> list[Idea]:
    """What to start next: ideas still in the pool, highest priority first."""
    query = select(Idea).where(Idea.status == IdeaStatus.pool)
    if brand_id:
        query = query.where(Idea.brand_id == brand_id)
    query = query.order_by(Idea.priority, Idea.updated_at.desc())
    return list(session.exec(query.limit(limit)).all())


def recent_publications(session: Session, brand_id: int | None = None,
                        limit: int = 5) -> list[tuple[Publication, Piece]]:
    """The last things that went out, newest first, with the piece each one was."""
    query = select(Publication, Piece).join(Piece, Piece.id == Publication.piece_id)
    if brand_id:
        query = query.where(Piece.brand_id == brand_id)
    return list(session.exec(query.order_by(Publication.posted_at.desc()).limit(limit)).all())


def piece_counts(session: Session, brand_id: int | None = None) -> dict[str, int]:
    query = select(Piece.stage, func.count(Piece.id)).group_by(Piece.stage)
    if brand_id:
        query = query.where(Piece.brand_id == brand_id)
    counts = {stage.value: total for stage, total in session.exec(query).all()}
    counts["total"] = sum(counts.values())
    return counts


def due_pieces(session: Session, on_or_before: date, brand_id: int | None = None) -> list[Piece]:
    """Everything scheduled up to a date and not published yet."""
    query = select(Piece).where(Piece.due_on.is_not(None),
                                Piece.due_on <= on_or_before,
                                Piece.stage != Stage.published)
    if brand_id:
        query = query.where(Piece.brand_id == brand_id)
    return list(session.exec(query.order_by(Piece.due_on)).all())


def idea_counts(session: Session, brand_id: int | None = None) -> dict[str, int]:
    query = select(Idea.status, func.count(Idea.id)).group_by(Idea.status)
    if brand_id:
        query = query.where(Idea.brand_id == brand_id)
    counts = {status.value: total for status, total in session.exec(query).all()}
    counts["total"] = sum(counts.values())
    return counts
