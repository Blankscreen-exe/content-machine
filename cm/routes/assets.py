"""A piece's assets: uploading, serving, and moving them to the trash.

Uploads come through the browser so they work from any device, not only the one running
the app. Pasting an image into the editor stores it the same way and answers with the
path to write into the markdown; the Assets panel takes several files at once, of any type
assets.py accepts, and answers by redrawing itself.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlmodel import Session

from .. import assets, crud, desktop, files, workspace
from ..database import get_session
from ..models import Piece
from ..settings import get_settings
from ..templating import templates
from .local import from_this_machine

router = APIRouter(prefix="/pieces/{piece_id}/assets")


def panel_context(request: Request, session: Session, piece: Piece) -> dict:
    """What the Assets panel needs; the piece page uses it for its first render too."""
    folder = workspace.piece_folder(session, piece)
    return {
        "assets": assets.listing(folder),
        "assets_folder": assets.folder_of(folder),
        "accepted": ",".join(sorted(assets.LIMITS)),
        # a folder opened on the server is only seen by someone sitting at it
        "can_open_folder": from_this_machine(request),
    }


@router.post("")
def paste(piece_id: int, file: UploadFile, session: Session = Depends(get_session)):
    """An image pasted or dropped into the editor: store it, return the path for the markdown."""
    folder = workspace.piece_folder(session, _piece(session, piece_id))
    try:
        name = assets.save(folder, file.filename or "", file.file, limits=assets.IMAGE_LIMITS)
    except assets.BadAsset as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    # The markdown keeps a relative path; the browser is told where to fetch it from.
    return {"name": name, "path": f"assets/{name}", "url": f"/pieces/{piece_id}/assets/{name}"}


@router.post("/files", response_class=HTMLResponse)
def upload(piece_id: int, request: Request, uploads: list[UploadFile] = File(...),
           session: Session = Depends(get_session)):
    """Files dropped on the Assets panel. Each is stored or refused on its own, so one
    wrong file does not stop the rest."""
    piece = _piece(session, piece_id)
    folder = workspace.piece_folder(session, piece)
    stored, refused = [], []
    for upload_file in uploads:
        try:
            stored.append(assets.save(folder, upload_file.filename or "", upload_file.file))
        except assets.BadAsset as exc:
            refused.append(str(exc))
    message = f"Added {', '.join(stored)}." if stored else ""
    return _panel(request, session, piece, message=message, problems=refused)


@router.get("/{name}")
def serve(piece_id: int, name: str, session: Session = Depends(get_session)):
    folder = workspace.piece_folder(session, _piece(session, piece_id))
    try:
        path = assets.path_of(folder, name)
    except (files.UnsafePath, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    # Answers range requests, so a video can be scrubbed without downloading all of it.
    return FileResponse(path, media_type=assets.media_type(path))


@router.post("/{name}/delete", response_class=HTMLResponse)
def trash(piece_id: int, name: str, request: Request, session: Session = Depends(get_session)):
    piece = _piece(session, piece_id)
    try:
        moved = workspace.trash_asset(session, piece, name)
    except (files.UnsafePath, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    return _panel(request, session, piece, message=f"Moved {name} to {_in_workspace(moved.parent)}.")


@router.post("/open", response_class=HTMLResponse)
def open_folder(piece_id: int, request: Request, session: Session = Depends(get_session)):
    """Open the assets folder in this computer's file manager, when asked from this computer."""
    piece = _piece(session, piece_id)
    if not from_this_machine(request):
        return _panel(request, session, piece,
                      problems=["The folder can only be opened on the machine running the app."])
    try:
        desktop.open_folder(assets.folder_of(workspace.piece_folder(session, piece)))
    except desktop.DesktopError as exc:
        return _panel(request, session, piece, problems=[str(exc)])
    return _panel(request, session, piece, message="Opened the folder.")


def _in_workspace(path: Path) -> str:
    """A path as it reads inside the workspace: the panel already shows the full folder,
    and an absolute path does not fit the sidebar."""
    workspace_dir = get_settings().workspace
    return str(path.relative_to(workspace_dir)) if path.is_relative_to(workspace_dir) else str(path)


def _piece(session: Session, piece_id: int) -> Piece:
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    return piece


def _panel(request: Request, session: Session, piece: Piece, message: str = "",
           problems: list[str] | None = None) -> HTMLResponse:
    context = {"request": request, "piece": piece, "message": message, "problems": problems or []}
    context |= panel_context(request, session, piece)
    return templates.TemplateResponse(request, "partials/assets_panel.html", context)
