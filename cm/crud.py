"""Database operations.

Both the web app and the CLI call these, so the rules live in one place.
"""
from __future__ import annotations

from datetime import date

from sqlmodel import Session, func, or_, select

from .models import (Brand, Event, Idea, IdeaStatus, Piece, PieceType, Publication,
                     Setting, Stage, now)
from .text import slugify

DEFAULT_SETTINGS = {"theme": "1996"}


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


def create_brand(session: Session, slug: str, name: str | None = None) -> Brand:
    existing = get_brand_by_slug(session, slug)
    if existing:
        return existing
    brand = Brand(slug=slug.strip(), name=(name or slug).strip())
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


def create_idea(session: Session, brand_id: int, **fields) -> Idea:
    idea = Idea(brand_id=brand_id, **fields)
    session.add(idea)
    session.commit()
    session.refresh(idea)
    record(session, "idea", idea.id, to_state=idea.status.value, note="created")
    session.commit()
    return idea


def update_idea(session: Session, idea: Idea, **fields) -> Idea:
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
                piece_type: PieceType | None = None, idea_id: int | None = None) -> list[Piece]:
    query = select(Piece)
    if brand_id:
        query = query.where(Piece.brand_id == brand_id)
    if stage:
        query = query.where(Piece.stage == stage)
    if piece_type:
        query = query.where(Piece.type == piece_type)
    if idea_id:
        query = query.where(Piece.idea_id == idea_id)
    # Dated work first, oldest due date at the top; undated work after it.
    query = query.order_by(Piece.due_on.is_(None), Piece.due_on, Piece.updated_at.desc())
    return list(session.exec(query).all())


def get_piece(session: Session, piece_id: int) -> Piece | None:
    return session.get(Piece, piece_id)


def unique_slug(session: Session, brand_id: int, title: str, piece_type: PieceType) -> str:
    """A slug no other piece of this brand has.

    The slug names the piece's folder, and pieces made from one idea share its title, so
    the type goes into the slug and a counter settles any remaining clash. Without this,
    two pieces could write into the same folder and overwrite each other's files.
    """
    base = f"{slugify(title)}-{slugify(PieceType(piece_type).value)}"
    taken = set(session.exec(select(Piece.slug).where(Piece.brand_id == brand_id)).all())
    slug, counter = base, 2
    while slug in taken:
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def create_piece(session: Session, brand_id: int, type: PieceType, title: str, **fields) -> Piece:
    fields["slug"] = unique_slug(session, brand_id, title, type)
    piece = Piece(brand_id=brand_id, type=type, title=title.strip(), **fields)
    session.add(piece)
    session.commit()
    session.refresh(piece)
    record(session, "piece", piece.id, to_state=piece.stage.value, note=f"created ({piece.type.value})")
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

    Its folder of drafts is left on disk: deleting the entry is not deleting the work.
    """
    for publication in session.exec(select(Publication).where(Publication.piece_id == piece.id)).all():
        session.delete(publication)
    session.flush()   # publications first, for the same reason as in delete_idea
    record(session, "piece", piece.id, to_state="deleted",
           from_state=piece.stage.value, note=piece.title)
    session.delete(piece)
    session.commit()


def record_publication(session: Session, piece: Piece, platform: str, url: str = "",
                       notes: str = "") -> Publication:
    """Record where a piece went out, and move it to published."""
    publication = Publication(piece_id=piece.id, platform=platform, url=url, notes=notes)
    session.add(publication)
    session.commit()
    session.refresh(publication)
    update_piece(session, piece, stage=Stage.published)
    return publication


def list_publications(session: Session, piece_id: int) -> list[Publication]:
    return list(session.exec(
        select(Publication).where(Publication.piece_id == piece_id).order_by(Publication.posted_at)
    ).all())


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
