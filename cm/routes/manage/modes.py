"""Modes: the stances each brand writes in, with the description sessions are given.

A brand's modes are a section of the brand's own page; adding and editing one opens in the
dialog, and every change answers by redrawing the brand's list of them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from ... import choices, crud, scaffold
from ...database import get_session
from ...models import Mode
from ..params import OptionalId
from . import page

router = APIRouter(prefix="/modes")


@router.get("")
def modes(session: Session = Depends(get_session), brand_id: OptionalId = None) -> RedirectResponse:
    """Where modes used to have a page of their own: on to the brand's page, where they are now."""
    if brand_id is None:
        brands = crud.list_brands(session)
        brand_id = brands[0].id if brands else None
    target = f"/manage/brands/{brand_id}#modes" if brand_id else "/manage/brands"
    return RedirectResponse(target, status_code=303)


@router.get("/new", response_class=HTMLResponse)
def mode_new(request: Request, brand_id: int, session: Session = Depends(get_session)):
    """The form for a new mode of a brand, opened in the dialog, starting from the questions
    a mode's description should answer."""
    if not crud.get_brand(session, brand_id):
        raise choices.ChoiceError("That brand does not exist.")
    return page.partial(request, "manage/mode_form.html", mode=None, brand_id=brand_id,
                        starter=scaffold.mode_starter())


@router.get("/{mode_id}/edit", response_class=HTMLResponse)
def mode_edit(mode_id: int, request: Request, session: Session = Depends(get_session)):
    mode = page.item_or_404(session, Mode, mode_id)
    return page.partial(request, "manage/mode_form.html", mode=mode, brand_id=mode.brand_id)


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


def panel_context(session: Session, brand_id: int) -> dict:
    """What a brand's list of modes needs; the brand page uses it for its first render too."""
    items = choices.all_items(session, Mode, brand_id=brand_id)
    return {
        "brand_id": brand_id,
        "modes": items,
        "usage": {mode.id: choices.usage(session, mode) for mode in items},
    }


def _list(request: Request, session: Session, brand_id: int) -> HTMLResponse:
    return page.partial(request, "manage/mode_list.html", **panel_context(session, brand_id))
