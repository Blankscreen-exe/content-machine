"""Idea pool: the list, the editor, and making a piece from an idea."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .. import crud
from ..database import get_session
from ..models import IdeaStatus, PieceType
from ..templating import STATUSES, TYPES, page_context, templates
from .params import OptionalId

router = APIRouter()


def _list_context(request: Request, session: Session, brand_id: int | None,
                  status: str | None, q: str | None) -> dict:
    return {
        "request": request,
        "ideas": crud.list_ideas(session, brand_id=brand_id,
                                 status=IdeaStatus(status) if status else None, search=q),
        "counts": crud.idea_counts(session, brand_id),
        "brand_id": brand_id,
        "status": status or "",
        "q": q or "",
    }


def _editor_context(request: Request, session: Session, idea) -> dict:
    return {
        "request": request,
        "idea": idea,
        "brand_id": idea.brand_id if idea else None,
        "pieces": crud.list_pieces(session, idea_id=idea.id) if idea else [],
        "brands": crud.list_brands(session),
        "statuses": STATUSES,
        "types": TYPES,
    }


@router.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session),
          brand_id: OptionalId = None, status: str | None = None, q: str | None = None):
    context = page_context(request, session, "ideas", brand_id)
    context |= _list_context(request, session, brand_id, status, q)
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/ideas", response_class=HTMLResponse)
def idea_list(request: Request, session: Session = Depends(get_session),
              brand_id: OptionalId = None, status: str | None = None, q: str | None = None):
    context = _list_context(request, session, brand_id, status, q) | {"oob": True}
    return templates.TemplateResponse(request, "partials/list.html", context)


@router.get("/ideas/new", response_class=HTMLResponse)
def idea_new(request: Request, session: Session = Depends(get_session), brand_id: OptionalId = None):
    context = _editor_context(request, session, None) | {"brand_id": brand_id}
    return templates.TemplateResponse(request, "partials/editor.html", context)


@router.get("/ideas/{idea_id}", response_class=HTMLResponse)
def idea_edit(idea_id: int, request: Request, session: Session = Depends(get_session)):
    idea = crud.get_idea(session, idea_id)
    if not idea:
        raise HTTPException(404, "idea not found")
    return templates.TemplateResponse(request, "partials/editor.html",
                                      _editor_context(request, session, idea))


@router.post("/ideas", response_class=HTMLResponse)
def idea_create(request: Request, session: Session = Depends(get_session),
                brand_id: int = Form(...), title: str = Form(...), angle: str = Form(""),
                talking_points: str = Form(""), notes: str = Form(""), mode: str = Form(""),
                source: str = Form(""), status: IdeaStatus = Form(IdeaStatus.pool),
                priority: int = Form(2)):
    crud.create_idea(session, brand_id=brand_id, title=title.strip(), angle=angle,
                     talking_points=talking_points, notes=notes, mode=mode, source=source,
                     status=status, priority=priority)
    return _refresh(request, session, brand_id)


@router.post("/ideas/{idea_id}", response_class=HTMLResponse)
def idea_update(idea_id: int, request: Request, session: Session = Depends(get_session),
                title: str = Form(...), angle: str = Form(""), talking_points: str = Form(""),
                notes: str = Form(""), mode: str = Form(""), source: str = Form(""),
                status: IdeaStatus = Form(IdeaStatus.pool), priority: int = Form(2)):
    idea = crud.get_idea(session, idea_id)
    if not idea:
        raise HTTPException(404, "idea not found")
    crud.update_idea(session, idea, title=title.strip(), angle=angle, talking_points=talking_points,
                     notes=notes, mode=mode, source=source, status=status, priority=priority)
    return _refresh(request, session, idea.brand_id)


@router.post("/ideas/{idea_id}/delete", response_class=HTMLResponse)
def idea_delete(idea_id: int, request: Request, session: Session = Depends(get_session)):
    idea = crud.get_idea(session, idea_id)
    if not idea:
        raise HTTPException(404, "idea not found")
    brand_id = idea.brand_id
    crud.delete_idea(session, idea)
    return _refresh(request, session, brand_id)


@router.post("/ideas/{idea_id}/pieces", response_class=HTMLResponse)
def piece_from_idea(idea_id: int, request: Request, session: Session = Depends(get_session),
                    type: PieceType = Form(...), due_on: date | None = Form(None)):
    """Make a piece from an idea, and promote the idea while we are at it."""
    idea = crud.get_idea(session, idea_id)
    if not idea:
        raise HTTPException(404, "idea not found")
    crud.create_piece(session, brand_id=idea.brand_id, type=type, title=idea.title,
                      idea_id=idea.id, due_on=due_on)
    if idea.status == IdeaStatus.pool:
        crud.update_idea(session, idea, status=IdeaStatus.promoted)
    return templates.TemplateResponse(request, "partials/editor.html",
                                      _editor_context(request, session, idea))


def _refresh(request: Request, session: Session, brand_id: int | None) -> HTMLResponse:
    """After a change: redraw the list, clear the editor, update the count."""
    context = _list_context(request, session, brand_id, None, None) | {"oob": True, "close_editor": True}
    return templates.TemplateResponse(request, "partials/list.html", context)
