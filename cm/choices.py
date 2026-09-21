"""The lists you pick from: piece types, platforms and each brand's modes.

They share one set of rules, kept here so each list does not grow its own version:

- Names are unique (within a brand, for modes), ignoring case and surrounding spaces.
- Lists are alphabetical.
- Turning an item off hides it from new choices. Records that already use it keep it,
  and their forms still offer it, so saving one never changes it by accident.
- An item can only be deleted when nothing uses it; otherwise it has to be turned off.
"""
from __future__ import annotations

from pathlib import PurePath

from sqlmodel import Session, func, select

from .files import GENERATED_FILES
from .models import Idea, Mode, Piece, PieceType, Platform, Publication

Choice = PieceType | Platform | Mode

# The column that points at each kind of item, for the "is it in use" check.
USED_BY = {
    PieceType: Piece.type_id,
    Platform: Publication.platform_id,
    Mode: Idea.mode_id,
}

# How to describe what is using it, when a delete is refused.
USED_BY_LABEL = {PieceType: "piece", Platform: "publish record", Mode: "idea"}


class ChoiceError(ValueError):
    """Something the person asked for breaks a rule above; the message says which."""


def _query(kind: type[Choice], brand_id: int | None):
    query = select(kind).order_by(func.lower(kind.name))
    if kind is Mode:
        query = query.where(Mode.brand_id == brand_id)
    return query


def all_items(session: Session, kind: type[Choice], brand_id: int | None = None) -> list[Choice]:
    """Every item, on or off, for managing them."""
    return list(session.exec(_query(kind, brand_id)).all())


def options(session: Session, kind: type[Choice], brand_id: int | None = None,
            current_id: int | None = None) -> list[Choice]:
    """What a form offers: the active items, plus the one already chosen if it is off."""
    query = _query(kind, brand_id).where((kind.active == True) | (kind.id == current_id))  # noqa: E712
    return list(session.exec(query).all())


def get(session: Session, kind: type[Choice], item_id: int) -> Choice | None:
    return session.get(kind, item_id)


def by_name(session: Session, kind: type[Choice], name: str,
            brand_id: int | None = None) -> Choice | None:
    query = _query(kind, brand_id).where(func.lower(kind.name) == name.strip().lower())
    return session.exec(query).first()


def create(session: Session, kind: type[Choice], name: str, brand_id: int | None = None,
           **fields) -> Choice:
    name = _clean_name(session, kind, name, brand_id)
    if kind is PieceType:
        fields["main_file"] = check_main_file(fields.get("main_file", "draft.md"))
        fields["char_limit"] = check_char_limit(fields.get("char_limit"))
    if kind is Mode:
        fields["brand_id"] = brand_id
    item = kind(name=name, **fields)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def update(session: Session, item: Choice, **fields) -> Choice:
    if "name" in fields:
        fields["name"] = _clean_name(session, type(item), fields["name"],
                                     getattr(item, "brand_id", None), keep=item)
    if "main_file" in fields:
        fields["main_file"] = check_main_file(fields["main_file"])
    if "char_limit" in fields:
        fields["char_limit"] = check_char_limit(fields["char_limit"])
    for key, value in fields.items():
        setattr(item, key, value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def usage(session: Session, item: Choice) -> int:
    """How many records use this item."""
    column = USED_BY[type(item)]
    return session.exec(select(func.count()).where(column == item.id)).one()


def delete(session: Session, item: Choice) -> None:
    used = usage(session, item)
    if used:
        label = USED_BY_LABEL[type(item)]
        raise ChoiceError(f"{item.name} is used by {used} {label}{'' if used == 1 else 's'}. "
                          "Turn it off instead, so it is no longer offered.")
    session.delete(item)
    session.commit()


def check_main_file(name: str) -> str:
    """A piece type's main draft: a plain markdown file name, and not one the app generates."""
    name = name.strip()
    if not name.endswith(".md") or PurePath(name).name != name or name == ".md":
        raise ChoiceError("The main file must be a plain file name ending in .md, like blog.md.")
    if name in GENERATED_FILES:
        raise ChoiceError(f"{name} is written by the app before every session; pick another name.")
    return name


def check_char_limit(limit: int | None) -> int | None:
    """A piece type's character limit: a positive number, or none at all."""
    if limit is not None and limit < 1:
        raise ChoiceError("A character limit is a number above zero, or left empty for none.")
    return limit


def _clean_name(session: Session, kind: type[Choice], name: str, brand_id: int | None,
                keep: Choice | None = None) -> str:
    name = " ".join(name.split())
    if not name:
        raise ChoiceError("A name is needed.")
    existing = by_name(session, kind, name, brand_id)
    if existing and existing is not keep:
        raise ChoiceError(f"There is already one called {existing.name}.")
    return name
