"""Editing the drafts in a piece folder.

Separate from the piece routes because this is file work, not database work: it is the
part that would change if drafts ever moved somewhere other than the filesystem.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .. import crud, files, workspace
from ..database import get_session
from ..models import Piece
from ..templating import templates

router = APIRouter(prefix="/pieces/{piece_id}/files")


def _piece_and_folder(session: Session, piece_id: int) -> tuple[Piece, Path]:
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    return piece, workspace.piece_folder(session, piece)


def pane_context(piece: Piece, folder: Path, name: str, text: str, fingerprint: str,
                 message: str = "", conflict: bool = False) -> dict:
    """Everything the editor pane needs. The piece page includes the same partial."""
    return {
        "piece": piece,
        "names": files.list_drafts(folder, files.MAIN_FILE[piece.type]),
        "name": name,
        "text": text,
        "fingerprint": fingerprint,
        "editable": files.is_editable(name),
        "message": message,
        "conflict": conflict,
    }


def editor_pane(request: Request, piece: Piece, folder: Path, name: str, text: str,
                fingerprint: str, message: str = "", conflict: bool = False) -> HTMLResponse:
    context = pane_context(piece, folder, name, text, fingerprint, message, conflict)
    return templates.TemplateResponse(request, "partials/editor_pane.html",
                                      {"request": request, **context})


@router.get("/{name}", response_class=HTMLResponse)
def open_file(piece_id: int, name: str, request: Request,
              session: Session = Depends(get_session)):
    piece, folder = _piece_and_folder(session, piece_id)
    try:
        text, fingerprint = files.read(folder, name)
    except files.UnsafePath as exc:
        raise HTTPException(400, str(exc)) from exc
    return editor_pane(request, piece, folder, name, text, fingerprint)


@router.post("/{name}", response_class=HTMLResponse)
def save_file(piece_id: int, name: str, request: Request,
              text: str = Form(""), fingerprint: str = Form(""), force: bool = Form(False),
              session: Session = Depends(get_session)):
    piece, folder = _piece_and_folder(session, piece_id)
    if not files.is_editable(name):
        raise HTTPException(400, f"{name} is generated and cannot be edited here")

    try:
        saved = files.write(folder, name, text, expected=fingerprint, force=force)
    except files.UnsafePath as exc:
        raise HTTPException(400, str(exc)) from exc
    except files.Conflict as conflict:
        # Keep what was typed on screen; offer to reload or to overwrite deliberately.
        return editor_pane(request, piece, folder, name, text, conflict.current_digest,
                           message=str(conflict), conflict=True)

    return editor_pane(request, piece, folder, name, text, saved, message="Saved")
