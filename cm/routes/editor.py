"""Editing the drafts in a piece folder.

Separate from the piece routes because this is file work, not database work: it is the
part that would change if drafts ever moved somewhere other than the filesystem.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .. import crud, desktop, files, frames, workspace
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


def opening_text(piece: Piece, folder: Path, name: str) -> tuple[str, str]:
    """A draft as the editor opens it, with its fingerprint.

    A video piece's frames file that does not exist yet opens on the template. The
    fingerprint stays that of the missing file, so the first save writes it as usual.
    """
    text, fingerprint = files.read(folder, name)
    if _is_frames_file(piece, name) and not files.exists(folder, name):
        text = frames.template()
    return text, fingerprint


def _is_frames_file(piece: Piece, name: str) -> bool:
    return piece.type.video and name == piece.type.main_file


def _frames_check(piece: Piece, name: str, text: str) -> dict:
    """For a frames file: a one-line summary, or what stops it being read as frames.
    Either way the text is saved; nothing typed is refused."""
    if not _is_frames_file(piece, name):
        return {}
    try:
        return {"frames_summary": frames.parse(text).summary()}
    except frames.FramesError as exc:
        return {"frames_problems": exc.problems}


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
        # a video's frames are not pasted anywhere, so their length in characters means nothing
        "count_characters": not piece.type.video,
        "char_limit": piece.type.char_limit,
        # the folder these drafts are in, opened on the machine running the app
        "open_folder_url": f"{base}/files/open",
        "can_open_folder": from_this_machine(request),
        **_frames_check(piece, name, text),
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
        text, fingerprint = opening_text(piece, folder, name)
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
