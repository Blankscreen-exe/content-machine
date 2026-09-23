"""Editing the drafts in a piece folder.

Separate from the piece routes because this is file work, not database work: it is the
part that would change if drafts ever moved somewhere other than the filesystem.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .. import crud, desktop, files, workspace
from ..database import get_session
from ..models import Piece
from ..templating import templates
from .local import from_this_machine

router = APIRouter(prefix="/pieces/{piece_id}/files")


def _piece_and_folder(session: Session, piece_id: int) -> tuple[Piece, Path]:
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    return piece, workspace.piece_folder(session, piece)


def pane_context(request: Request, piece: Piece, folder: Path, name: str, text: str,
                 fingerprint: str, message: str = "", conflict: bool = False) -> dict:
    """The editor pane pointed at one of a piece's draft files. The piece page includes
    the same partial, so this is used for its first render too."""
    base = f"/pieces/{piece.id}"
    return {"pane": {
        "tabs": [{"label": other, "url": f"{base}/files/{other}", "on": other == name}
                 for other in files.list_drafts(folder, piece.type.main_file)],
        "save_url": f"{base}/files/{name}",
        "open_url": f"{base}/files/{name}",
        "text": text,
        "fingerprint": fingerprint,
        "editable": files.is_editable(name),
        "readonly_reason": f"{name} is generated before every session and cannot be edited here.",
        "message": message,
        "conflict": conflict,
        # pasted images are stored in the piece folder and served from there
        "upload_url": f"{base}/assets",
        "assets_url": f"{base}/assets/",
        "char_limit": piece.type.char_limit,
        # the folder these drafts are in, opened on the machine running the app
        "open_folder_url": f"{base}/files/open",
        "can_open_folder": from_this_machine(request),
    }}


def editor_pane(request: Request, piece: Piece, folder: Path, name: str, text: str,
                fingerprint: str, message: str = "", conflict: bool = False) -> HTMLResponse:
    context = pane_context(request, piece, folder, name, text, fingerprint, message, conflict)
    return templates.TemplateResponse(request, "partials/editor_pane.html",
                                      {"request": request, **context})


# Declared before `/{name}`, which would otherwise read "open" as a file name.
@router.post("/open", response_class=HTMLResponse)
def open_folder(piece_id: int, request: Request, session: Session = Depends(get_session)):
    """Open the piece's folder — its drafts and assets — in this computer's file manager."""
    piece, folder = _piece_and_folder(session, piece_id)
    if not from_this_machine(request):
        return _message(request, "The folder can only be opened on the machine running the app.")
    workspace.ensure_folder(session, piece)
    try:
        desktop.open_folder(folder)
    except desktop.DesktopError as exc:
        return _message(request, str(exc))
    return _message(request, f"Opened {folder}")


def _message(request: Request, message: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "partials/message.html",
                                      {"request": request, "message": message})


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
