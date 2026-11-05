"""Idea pool: the list, each idea's own page, and making a piece from an idea."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from .. import choices, crud
from ..database import get_session
from ..models import Idea, IdeaStatus, Mode, PieceType
from ..templating import STATUSES, page_context, templates
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


def _idea_context(request: Request, session: Session, idea: Idea | None,
                  brand_id: int | None = None) -> dict:
    """What an idea's page and its parts need. `brand_id` is the brand a new idea will
    belong to, when the list it came from was showing one."""
    brand_id = idea.brand_id if idea else brand_id
    return {
        "request": request,
        "idea": idea,
        "brand_id": brand_id,
        "brand_slug": crud.brand_slug(session, brand_id) if brand_id else "",
        "modes": _mode_options(session, brand_id, idea.mode_id if idea else None),
        "pieces": crud.list_pieces(session, idea_id=idea.id) if idea else [],
        "brands": crud.list_brands(session),
        "statuses": STATUSES,
        "types": choices.options(session, PieceType),
    }


def _mode_options(session: Session, brand_id: int | None, current_id: int | None) -> list[Mode]:
    """A brand's modes. With no brand chosen yet there is nothing to offer."""
    if brand_id is None:
        return []
    return choices.options(session, Mode, brand_id=brand_id, current_id=current_id)


@router.get("/ideas", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session),
          brand_id: OptionalId = None, status: str | None = None, q: str | None = None):
    context = page_context(request, session, "ideas", brand_id)
    context |= _list_context(request, session, brand_id, status, q)
    return templates.TemplateResponse(request, "ideas.html", context)


# Declared before `/ideas/{idea_id}`, which would otherwise read "list" as an id.
@router.get("/ideas/list", response_class=HTMLResponse)
def idea_list(request: Request, session: Session = Depends(get_session),
              brand_id: OptionalId = None, status: str | None = None, q: str | None = None):
    context = _list_context(request, session, brand_id, status, q) | {"oob": True}
    return templates.TemplateResponse(request, "partials/list.html", context)


@router.get("/ideas/new", response_class=HTMLResponse)
def idea_new(request: Request, session: Session = Depends(get_session), brand_id: OptionalId = None):
    """A new idea's page: the form, with nothing made from it yet."""
    return _page(request, session, None, brand_id)


# Declared before `/ideas/{idea_id}`, which would otherwise read "mode-field" as an id.
@router.get("/ideas/mode-field", response_class=HTMLResponse)
def mode_field(request: Request, session: Session = Depends(get_session),
               brand_id: OptionalId = None):
    """The mode dropdown for a new idea, redrawn when its brand is picked."""
    return templates.TemplateResponse(
        request, "partials/mode_field.html",
        {"request": request, "idea": None, "brand_id": brand_id,
         "modes": _mode_options(session, brand_id, None)},
    )


@router.get("/ideas/{idea_id}", response_class=HTMLResponse)
def idea_page(idea_id: int, request: Request, session: Session = Depends(get_session)):
    """One idea: its details, and the pieces made from it beside them."""
    return _page(request, session, _idea(session, idea_id), None)


@router.post("/ideas", response_class=HTMLResponse)
def idea_create(session: Session = Depends(get_session),
                brand_id: int = Form(...), title: str = Form(...), angle: str = Form(""),
                talking_points: str = Form(""), notes: str = Form(""),
                mode_id: OptionalId = Form(None), source: str = Form(""),
                status: IdeaStatus = Form(IdeaStatus.pool), priority: int = Form(2)):
    """A new idea opens on its own page, where pieces can be made from it."""
    idea = crud.create_idea(session, brand_id=brand_id, title=title.strip(), angle=angle,
                            talking_points=talking_points, notes=notes, mode_id=mode_id,
                            source=source, status=status, priority=priority)
    return Response(status_code=204, headers={"HX-Redirect": f"/ideas/{idea.id}"})


@router.post("/ideas/{idea_id}", response_class=HTMLResponse)
def idea_update(idea_id: int, request: Request, session: Session = Depends(get_session),
                title: str = Form(...), angle: str = Form(""), talking_points: str = Form(""),
                notes: str = Form(""), mode_id: OptionalId = Form(None), source: str = Form(""),
                status: IdeaStatus = Form(IdeaStatus.pool), priority: int = Form(2)):
    """Saving redraws the form, and the heading, which shows the status and priority."""
    idea = _idea(session, idea_id)
    crud.update_idea(session, idea, title=title.strip(), angle=angle, talking_points=talking_points,
                     notes=notes, mode_id=mode_id, source=source, status=status, priority=priority)
    context = _idea_context(request, session, idea) | {"message": "Saved", "head_oob": True}
    return templates.TemplateResponse(request, "partials/idea_form.html", context)


@router.post("/ideas/{idea_id}/delete", response_class=HTMLResponse)
def idea_delete(idea_id: int, request: Request, session: Session = Depends(get_session),
                brand_id: OptionalId = Form(None), origin: Literal["list", "page"] = Form("list")):
    """`brand_id` is the brand the list is showing, not the idea's own. From the idea's own
    page, which no longer exists afterwards, it goes back to its brand's list."""
    idea = _idea(session, idea_id)
    own_brand_id = idea.brand_id
    crud.delete_idea(session, idea)
    if origin == "page":
        return Response(status_code=204, headers={"HX-Redirect": f"/ideas?brand_id={own_brand_id}"})
    return _refresh(request, session, brand_id)


@router.post("/ideas/{idea_id}/pieces", response_class=HTMLResponse)
def piece_from_idea(idea_id: int, request: Request, session: Session = Depends(get_session),
                    type_id: int = Form(...), due_on: date | None = Form(None)):
    """Make a piece from an idea, and promote the idea while we are at it."""
    idea = _idea(session, idea_id)
    if not choices.get(session, PieceType, type_id):
        raise choices.ChoiceError("That piece type does not exist.")
    crud.create_piece(session, brand_id=idea.brand_id, type_id=type_id, title=idea.title,
                      idea_id=idea.id, due_on=due_on)
    if idea.status == IdeaStatus.pool:
        crud.update_idea(session, idea, status=IdeaStatus.promoted)
    return templates.TemplateResponse(request, "partials/idea_pieces.html",
                                      _idea_context(request, session, idea) | {"head_oob": True})


def _idea(session: Session, idea_id: int) -> Idea:
    idea = crud.get_idea(session, idea_id)
    if not idea:
        raise HTTPException(404, "idea not found")
    return idea


def _page(request: Request, session: Session, idea: Idea | None, brand_id: int | None) -> HTMLResponse:
    context = page_context(request, session, "ideas", idea.brand_id if idea else brand_id)
    context |= _idea_context(request, session, idea, brand_id)
    return templates.TemplateResponse(request, "idea.html", context)


def _refresh(request: Request, session: Session, brand_id: int | None) -> HTMLResponse:
    """After a delete from the list: redraw it and its count."""
    context = _list_context(request, session, brand_id, None, None) | {"oob": True}
    return templates.TemplateResponse(request, "partials/list.html", context)
