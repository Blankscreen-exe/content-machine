"""Platforms: where pieces get published, offered when recording a publish."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ... import choices
from ...database import get_session
from ...models import Platform
from . import page

router = APIRouter(prefix="/platforms")


@router.get("", response_class=HTMLResponse)
def platforms(request: Request, session: Session = Depends(get_session)):
    return page.render(request, session, "platforms", "manage/platforms.html",
                       **_list_context(session))


@router.post("", response_class=HTMLResponse)
def platform_create(request: Request, name: str = Form(...),
                    session: Session = Depends(get_session)):
    choices.create(session, Platform, name)
    return _list(request, session)


@router.post("/{platform_id}", response_class=HTMLResponse)
def platform_update(platform_id: int, request: Request, name: str = Form(...),
                    session: Session = Depends(get_session)):
    choices.update(session, page.item_or_404(session, Platform, platform_id), name=name)
    return _list(request, session)


@router.post("/{platform_id}/active", response_class=HTMLResponse)
def platform_active(platform_id: int, request: Request, active: bool = Form(...),
                    session: Session = Depends(get_session)):
    choices.update(session, page.item_or_404(session, Platform, platform_id), active=active)
    return _list(request, session)


@router.post("/{platform_id}/delete", response_class=HTMLResponse)
def platform_delete(platform_id: int, request: Request, session: Session = Depends(get_session)):
    choices.delete(session, page.item_or_404(session, Platform, platform_id))
    return _list(request, session)


def _list_context(session: Session) -> dict:
    items = choices.all_items(session, Platform)
    return {"platforms": items, "usage": {p.id: choices.usage(session, p) for p in items}}


def _list(request: Request, session: Session) -> HTMLResponse:
    return page.partial(request, "manage/platform_list.html", **_list_context(session))
