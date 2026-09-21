"""Images pasted into a draft.

They are stored in the piece's own `assets/` folder and referenced from the markdown by a
relative path, so the folder stays self-contained. These routes exist because a browser
needs an address to display one.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import Session

from .. import crud, files, workspace
from ..database import get_session

router = APIRouter(prefix="/pieces/{piece_id}/assets")


def _folder(session: Session, piece_id: int):
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    return workspace.piece_folder(session, piece)


@router.post("")
async def upload(piece_id: int, request: Request, file: UploadFile,
                 session: Session = Depends(get_session)):
    """Store an image and return the path to write into the markdown."""
    folder = _folder(session, piece_id)
    try:
        name = files.save_image(folder, file.filename or "", await file.read())
    except files.BadImage as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    # The markdown keeps a relative path; the browser is told where to fetch it from.
    return {"name": name, "path": f"assets/{name}", "url": f"/pieces/{piece_id}/assets/{name}"}


@router.get("/{name}")
def serve(piece_id: int, name: str, session: Session = Depends(get_session)):
    folder = _folder(session, piece_id)
    try:
        return FileResponse(files.image_path(folder, name))
    except files.UnsafePath as exc:
        raise HTTPException(404, str(exc)) from exc
