"""The Render panel on a video piece's page: start a draft or final render, and follow it.

Rendering runs on this machine whichever device asked for it, so any device may start one.
While a render runs, the panel asks for itself again every second; when the render is
done, it tells the Assets panel to redraw so the new video appears there.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .. import crud, frames, render_jobs, renders, video
from ..database import get_session
from ..models import Piece
from ..templating import templates

router = APIRouter(prefix="/pieces/{piece_id}/render")

# The event the Assets panel listens for, to redraw once a video has landed in it.
ASSETS_CHANGED = "assets-changed"


def panel_context(piece: Piece) -> dict:
    """What the Render panel needs; the piece page uses it for its first render too."""
    return {"render_job": render_jobs.latest(piece.id)}


@router.get("", response_class=HTMLResponse)
def panel(piece_id: int, request: Request, following: bool = False,
          session: Session = Depends(get_session)):
    """The panel as it stands. `following` is set by a panel that was showing a render
    running: if that render has now finished, the Assets panel is told to redraw."""
    piece = _video_piece(session, piece_id)
    response = _panel(request, piece)
    job = render_jobs.latest(piece.id)
    if following and job and job.state == "done":
        response.headers["HX-Trigger"] = ASSETS_CHANGED
    return response


@router.post("", response_class=HTMLResponse)
def start(piece_id: int, request: Request, draft: bool = Form(False),
          session: Session = Depends(get_session)):
    piece = _video_piece(session, piece_id)
    try:
        render_jobs.start(renders.plan(session, piece), draft=draft)
    except frames.FramesError as exc:
        return _panel(request, piece, [f"{piece.type.main_file} needs fixing first:", *exc.problems])
    except (video.RenderError, render_jobs.AlreadyRendering) as exc:
        return _panel(request, piece, [str(exc)])
    return _panel(request, piece)


def _video_piece(session: Session, piece_id: int) -> Piece:
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    if not piece.type.video:
        raise HTTPException(400, f"{piece.title} is not a video piece")
    return piece


def _panel(request: Request, piece: Piece, problems: list[str] | None = None) -> HTMLResponse:
    context = {"request": request, "piece": piece, "problems": problems or [], **panel_context(piece)}
    return templates.TemplateResponse(request, "partials/render_panel.html", context)
