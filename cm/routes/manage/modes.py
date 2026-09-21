"""Modes: the stances each brand writes in, with the description sessions are given."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ... import choices, crud, scaffold
from ...database import get_session
from ...models import Mode
from ..params import OptionalId
from . import page

router = APIRouter(prefix="/modes")


@router.get("", response_class=HTMLResponse)
def modes(request: Request, session: Session = Depends(get_session), brand_id: OptionalId = None):
    """One brand's modes. With none picked, the first brand's, so the page is never empty."""
    brands = crud.list_brands(session)
    if brand_id is None and brands:
        brand_id = brands[0].id
    return page.render(request, session, "modes", "manage/modes.html",
                       brands=brands, **_list_context(session, brand_id))


@router.post("", response_class=HTMLResponse)
def mode_create(request: Request, brand_id: int = Form(...), name: str = Form(...),
                description: str = Form(""), session: Session = Depends(get_session)):
    if not crud.get_brand(session, brand_id):
        raise choices.ChoiceError("That brand does not exist.")
    choices.create(session, Mode, name, brand_id=brand_id, description=description)
    return _list(request, session, brand_id)


@router.post("/{mode_id}", response_class=HTMLResponse)
def mode_update(mode_id: int, request: Request, name: str = Form(...),
                description: str = Form(""), session: Session = Depends(get_session)):
    mode = page.item_or_404(session, Mode, mode_id)
    choices.update(session, mode, name=name, description=description)
    return _list(request, session, mode.brand_id)


@router.post("/{mode_id}/active", response_class=HTMLResponse)
def mode_active(mode_id: int, request: Request, active: bool = Form(...),
                session: Session = Depends(get_session)):
    mode = page.item_or_404(session, Mode, mode_id)
    choices.update(session, mode, active=active)
    return _list(request, session, mode.brand_id)


@router.post("/{mode_id}/delete", response_class=HTMLResponse)
def mode_delete(mode_id: int, request: Request, session: Session = Depends(get_session)):
    mode = page.item_or_404(session, Mode, mode_id)
    brand_id = mode.brand_id
    choices.delete(session, mode)
    return _list(request, session, brand_id)


def _list_context(session: Session, brand_id: int | None) -> dict:
    items = choices.all_items(session, Mode, brand_id=brand_id) if brand_id else []
    return {
        "brand_id": brand_id,
        "modes": items,
        "usage": {mode.id: choices.usage(session, mode) for mode in items},
        "starter": scaffold.mode_starter(),      # what the add form's description starts as
    }


def _list(request: Request, session: Session, brand_id: int) -> HTMLResponse:
    return page.partial(request, "manage/mode_list.html", **_list_context(session, brand_id))
