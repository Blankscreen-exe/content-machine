"""A piece's history, fetched each time its panel is opened."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .. import crud, history
from ..database import get_session
from ..templating import templates

router = APIRouter(prefix="/pieces/{piece_id}/history")


@router.get("", response_class=HTMLResponse)
def piece_history(piece_id: int, request: Request, session: Session = Depends(get_session)):
    if not crud.get_piece(session, piece_id):
        raise HTTPException(404, "piece not found")
    return templates.TemplateResponse(request, "partials/history_entries.html",
                                      {"request": request, "entries": history.of_piece(session, piece_id)})
