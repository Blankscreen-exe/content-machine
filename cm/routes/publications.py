"""Recording where a piece was published, from its own page."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .. import crud, schedule
from ..database import get_session
from ..dates import moment_on
from ..models import Piece
from ..templating import templates

router = APIRouter(prefix="/pieces/{piece_id}/publications")


def publications_context(session: Session, piece: Piece) -> dict:
    """What the Published panel needs; the piece page uses it for its first render too."""
    return {
        "publications": crud.list_publications(session, piece.id),
        "platforms": crud.known_platforms(session),
        "today": date.today(),
    }


@router.post("", response_class=HTMLResponse)
def publication_create(piece_id: int, request: Request, session: Session = Depends(get_session),
                       platform: str = Form(...), url: str = Form(""),
                       posted_on: date = Form(...)):
    piece = _piece(session, piece_id)
    crud.record_publication(session, piece, platform=platform, url=url,
                            posted_at=moment_on(posted_on))
    # recording moves the piece to published, which the heading and the due count show
    return _panel(request, session, piece, redraw_head=True)


@router.post("/{publication_id}/delete", response_class=HTMLResponse)
def publication_delete(piece_id: int, publication_id: int, request: Request,
                       session: Session = Depends(get_session)):
    piece = _piece(session, piece_id)
    publication = crud.get_publication(session, publication_id)
    if not publication or publication.piece_id != piece.id:
        raise HTTPException(404, "publication not found")
    crud.delete_publication(session, publication)
    return _panel(request, session, piece, redraw_head=False)


def _piece(session: Session, piece_id: int) -> Piece:
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    return piece


def _panel(request: Request, session: Session, piece: Piece, redraw_head: bool) -> HTMLResponse:
    context = {"request": request, "piece": piece, "redraw_head": redraw_head,
               "idea": crud.get_idea(session, piece.idea_id) if piece.idea_id else None,
               "due": schedule.due(session, date.today(), piece.brand_id)}
    context |= publications_context(session, piece)
    return templates.TemplateResponse(request, "partials/publications_response.html", context)
