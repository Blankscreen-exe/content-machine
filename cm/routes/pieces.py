"""Pieces: the things that actually get published, each with a type, a stage and a due date."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from .. import crud, files, schedule, terminals, workspace
from ..database import get_session
from ..models import PieceType, Stage
from ..templating import STAGES, TYPES, page_context, templates
from .editor import pane_context
from .publications import publications_context
from .params import OptionalId

router = APIRouter(prefix="/pieces")

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}

# Where the details form was opened, which decides what saving it redraws.
Origin = Literal["list", "page"]


def _list_context(request: Request, session: Session, brand_id: int | None,
                  stage: str | None, type: str | None) -> dict:
    return {
        "request": request,
        "pieces": crud.list_pieces(session, brand_id=brand_id,
                                   stage=Stage(stage) if stage else None,
                                   piece_type=PieceType(type) if type else None),
        "counts": crud.piece_counts(session, brand_id),
        "brand_id": brand_id,
        "stage": stage or "",
        "type": type or "",
        "stages": STAGES,
        "types": TYPES,
        "today": date.today(),
        "due": schedule.due(session, date.today(), brand_id),
    }


@router.get("", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session),
          brand_id: OptionalId = None, stage: str | None = None, type: str | None = None):
    context = page_context(request, session, "pieces", brand_id)
    context |= _list_context(request, session, brand_id, stage, type)
    return templates.TemplateResponse(request, "pieces.html", context)


@router.get("/list", response_class=HTMLResponse)
def piece_list(request: Request, session: Session = Depends(get_session),
               brand_id: OptionalId = None, stage: str | None = None, type: str | None = None):
    context = _list_context(request, session, brand_id, stage, type) | {"oob": True}
    return templates.TemplateResponse(request, "partials/pieces.html", context)


# `/new` has to be declared before `/{piece_id}`: FastAPI takes the first path that
# matches, and would read "new" as a piece id and reject it.
@router.get("/new", response_class=HTMLResponse)
def piece_new(request: Request, session: Session = Depends(get_session),
              brand_id: OptionalId = None, idea_id: OptionalId = None, title: str = ""):
    return templates.TemplateResponse(
        request, "partials/piece_editor.html",
        {"request": request, "piece": None, "origin": "list", "brand_id": brand_id,
         "view_brand_id": brand_id, "idea_id": idea_id, "idea_title": title,
         "brands": crud.list_brands(session), "stages": STAGES, "types": TYPES},
    )


@router.get("/{piece_id}", response_class=HTMLResponse)
def piece_page(piece_id: int, request: Request, session: Session = Depends(get_session)):
    """One piece: its details, its drafts, and the button that opens a session on it."""
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")

    folder = workspace.piece_folder(session, piece)
    main = files.MAIN_FILE[piece.type]
    text, fingerprint = files.read(folder, main)

    context = page_context(request, session, "pieces", piece.brand_id)
    context |= {
        "piece": piece,
        "idea": crud.get_idea(session, piece.idea_id) if piece.idea_id else None,
        "folder": folder,
        "images": files.images(folder),
        "stages": STAGES,
        "types": TYPES,
    }
    context |= publications_context(session, piece)
    context |= pane_context(piece, folder, main, text, fingerprint)
    return templates.TemplateResponse(request, "piece.html", context)


@router.get("/{piece_id}/form", response_class=HTMLResponse)
def piece_form(piece_id: int, request: Request, session: Session = Depends(get_session),
               origin: Origin = "list", brand_id: OptionalId = None):
    """The details form. `/pieces/{id}` itself is reserved for the piece's own page.

    `brand_id` is the brand the list is showing, carried so saving redraws that view.
    """
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    return templates.TemplateResponse(
        request, "partials/piece_editor.html",
        {"request": request, "piece": piece, "origin": origin, "brand_id": piece.brand_id,
         "view_brand_id": brand_id, "stages": STAGES, "types": TYPES},
    )


@router.post("", response_class=HTMLResponse)
def piece_create(request: Request, session: Session = Depends(get_session),
                 brand_id: int = Form(...), title: str = Form(...), type: PieceType = Form(...),
                 stage: Stage = Form(Stage.not_started), due_on: date | None = Form(None),
                 notes: str = Form(""), idea_id: OptionalId = Form(None),
                 view_brand_id: OptionalId = Form(None)):
    crud.create_piece(session, brand_id=brand_id, type=type, title=title, stage=stage,
                      due_on=due_on, notes=notes, idea_id=idea_id)
    return _refresh(request, session, view_brand_id)


@router.post("/{piece_id}", response_class=HTMLResponse)
def piece_update(piece_id: int, request: Request, session: Session = Depends(get_session),
                 title: str = Form(...), type: PieceType = Form(...),
                 stage: Stage = Form(Stage.not_started), due_on: date | None = Form(None),
                 notes: str = Form(""), origin: Origin = Form("list"),
                 view_brand_id: OptionalId = Form(None)):
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    crud.update_piece(session, piece, title=title.strip(), type=type, stage=stage,
                      due_on=due_on, notes=notes)
    if origin == "page":
        return templates.TemplateResponse(
            request, "partials/piece_head.html",
            {"request": request, "piece": piece, "oob": True,
             "idea": crud.get_idea(session, piece.idea_id) if piece.idea_id else None,
             "due": schedule.due(session, date.today(), piece.brand_id)},
        )
    return _refresh(request, session, view_brand_id)


@router.post("/{piece_id}/stage", response_class=HTMLResponse)
def piece_stage(piece_id: int, request: Request, session: Session = Depends(get_session),
                stage: Stage = Form(...), brand_id: OptionalId = Form(None)):
    """Stage changes happen inline in the list, so this keeps the current filters."""
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    crud.update_piece(session, piece, stage=stage)
    context = _list_context(request, session, brand_id, None, None) | {"oob": True}
    return templates.TemplateResponse(request, "partials/pieces.html", context)


SESSION_PROMPT = "Read brief.md first, then help me with this piece."


@router.post("/{piece_id}/session", response_class=HTMLResponse)
def piece_session(piece_id: int, request: Request, session: Session = Depends(get_session)):
    """Open a terminal in the piece's folder with Claude running.

    Refused unless the request came from this machine: the app can be served on the local
    network, and nothing on the network should be able to start processes here.
    """
    if request.client is None or request.client.host not in LOCAL_HOSTS:
        return _session_message(request, "Terminal sessions can only be started on this machine.")

    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")

    folder = workspace.write_brief(session, piece).parent
    try:
        terminals.open_terminal(
            cwd=folder,
            title=f"{piece.title} ({piece.type.value})",
            command=terminals.claude_command(SESSION_PROMPT),
            key=crud.get_settings_map(session).get("terminal"),
        )
    except terminals.TerminalError as exc:
        return _session_message(request, str(exc))

    return _session_message(request, f"Session opened in {folder}")


def _session_message(request: Request, message: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "partials/message.html",
                                      {"request": request, "message": message})


@router.post("/{piece_id}/delete", response_class=HTMLResponse)
def piece_delete(piece_id: int, request: Request, session: Session = Depends(get_session),
                 origin: Origin = Form("list"), brand_id: OptionalId = Form(None)):
    """`brand_id` is the brand the list is showing, not the piece's own."""
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    own_brand_id = piece.brand_id
    try:
        workspace.delete_piece(session, piece)
    except OSError as exc:
        raise HTTPException(409, f"Its folder could not be moved to the trash ({exc.strerror}). "
                                 "Close anything using it, such as a terminal session, "
                                 "and try again.") from exc
    if origin == "page":
        # the page being looked at no longer exists, so go back to its brand's list
        return Response(status_code=204,
                        headers={"HX-Redirect": f"/pieces?brand_id={own_brand_id}"})
    return _refresh(request, session, brand_id)


def _refresh(request: Request, session: Session, brand_id: int | None) -> HTMLResponse:
    context = _list_context(request, session, brand_id, None, None) | {"oob": True, "close_editor": True}
    return templates.TemplateResponse(request, "partials/pieces.html", context)
