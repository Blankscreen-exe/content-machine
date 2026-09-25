"""Piece types: what can be made, and the draft file each one opens on."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ... import choices
from ...database import get_session
from ...models import PieceType
from ..params import OptionalInt
from . import page

router = APIRouter(prefix="/types")


@router.get("", response_class=HTMLResponse)
def types(request: Request, session: Session = Depends(get_session)):
    return page.render(request, session, "types", "manage/types.html", **_list_context(session))


@router.post("", response_class=HTMLResponse)
def type_create(request: Request, name: str = Form(...), main_file: str = Form(...),
                char_limit: OptionalInt = Form(None), video: bool = Form(False),
                session: Session = Depends(get_session)):
    choices.create(session, PieceType, name, main_file=main_file, char_limit=char_limit, video=video)
    return _list(request, session)


@router.post("/{type_id}", response_class=HTMLResponse)
def type_update(type_id: int, request: Request, name: str = Form(...),
                main_file: str = Form(...), char_limit: OptionalInt = Form(None),
                video: bool = Form(False), session: Session = Depends(get_session)):
    """Renaming is safe: pieces point at the type, and their folders keep the name they got.

    An unticked checkbox is not sent at all, so a missing `video` means "not video".
    """
    choices.update(session, page.item_or_404(session, PieceType, type_id),
                   name=name, main_file=main_file, char_limit=char_limit, video=video)
    return _list(request, session)


@router.post("/{type_id}/active", response_class=HTMLResponse)
def type_active(type_id: int, request: Request, active: bool = Form(...),
                session: Session = Depends(get_session)):
    choices.update(session, page.item_or_404(session, PieceType, type_id), active=active)
    return _list(request, session)


@router.post("/{type_id}/delete", response_class=HTMLResponse)
def type_delete(type_id: int, request: Request, session: Session = Depends(get_session)):
    choices.delete(session, page.item_or_404(session, PieceType, type_id))
    return _list(request, session)


def _list_context(session: Session) -> dict:
    items = choices.all_items(session, PieceType)
    return {"types": items, "usage": {t.id: choices.usage(session, t) for t in items}}


def _list(request: Request, session: Session) -> HTMLResponse:
    return page.partial(request, "manage/type_list.html", **_list_context(session))
