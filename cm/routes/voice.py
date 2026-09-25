"""The Voice page of a video piece: record takes over the draft, choose one, line it up,
trim it, and pick the music.

Recording happens in the browser (voice.js); this saves what it sends, serves the takes
back, and keeps the choices in the piece's voice/mix.json (voice.py). Takes and settings
change by ordinary form posts that come back to the page, so the page always shows what
is saved.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import Session

from .. import assets, crud, files, frames, renders, resources, timing, voice, workspace
from ..database import get_session
from ..formats import FPS
from ..models import Piece
from ..settings import get_settings
from ..templating import page_context, templates
from .local import opened_at_loopback
from .serving import stored_file

router = APIRouter(prefix="/pieces/{piece_id}/voice")


@router.get("", response_class=HTMLResponse)
def page(piece_id: int, request: Request, saved: bool = False, session: Session = Depends(get_session)):
    piece = _video_piece(session, piece_id)
    return _page(request, session, piece, message="Saved." if saved else "")


@router.post("/takes")
def upload_take(piece_id: int, take: UploadFile = File(...), session: Session = Depends(get_session)):
    """A take recorded in the browser. It becomes the one used, lined up at the start."""
    piece = _video_piece(session, piece_id)
    try:
        name = voice.save_take(workspace.piece_folder(session, piece), take.filename or "", take.file)
    except (assets.BadAsset, voice.MixError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"name": name}


@router.get("/takes/{name}")
def serve_take(piece_id: int, name: str, session: Session = Depends(get_session)):
    piece = _video_piece(session, piece_id)
    try:
        path = voice.take_path(workspace.piece_folder(session, piece), name)
    except (files.UnsafePath, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    return stored_file(path)


@router.post("/takes/{name}/delete")
def delete_take(piece_id: int, name: str, request: Request, session: Session = Depends(get_session)):
    piece = _video_piece(session, piece_id)
    folder = workspace.piece_folder(session, piece)
    trash = get_settings().trash_dir / crud.brand_slug(session, piece.brand_id) / folder.name / voice.FOLDER
    try:
        voice.trash_take(folder, name, trash)
    except (files.UnsafePath, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    except voice.MixError as exc:
        return _page(request, session, piece, problems=[str(exc)])
    return RedirectResponse(f"/pieces/{piece.id}/voice?saved=true", status_code=303)


@router.post("/mix")
def save_mix(piece_id: int, request: Request, take: str = Form(""), offset: str = Form("0"),
             trim_start: str = Form("0"), trim_end: str = Form(""), volume: str = Form("1"),
             music: str = Form(""), music_volume: str = Form("0.12"), session: Session = Depends(get_session)):
    piece = _video_piece(session, piece_id)
    folder = workspace.piece_folder(session, piece)
    slug = crud.brand_slug(session, piece.brand_id)
    try:
        if take and take not in {t.name for t in voice.takes(folder)}:
            raise voice.MixError(f"There is no take called {take}.")
        if music and music not in {m.name for m in resources.listing(slug)["music"]}:
            raise voice.MixError(f"The brand's music has no {music}.")
        voice.write_mix(folder, voice.Mix(
            take=take or None, offset=_number("Offset", offset), trim_start=_number("Trim start", trim_start),
            trim_end=_number("Trim end", trim_end) if trim_end.strip() else None, volume=_number("Volume", volume),
            music=music or None, music_volume=_number("Music volume", music_volume)))
    except voice.MixError as exc:
        return _page(request, session, piece, problems=[str(exc)])
    return RedirectResponse(f"/pieces/{piece.id}/voice?saved=true", status_code=303)


def _number(label: str, text: str) -> float:
    try:
        return float(text)
    except ValueError as exc:
        raise voice.MixError(f"{label} should be a number, not {text!r}.") from exc


def _video_piece(session: Session, piece_id: int) -> Piece:
    piece = crud.get_piece(session, piece_id)
    if not piece:
        raise HTTPException(404, "piece not found")
    if not piece.type.video:
        raise HTTPException(400, f"{piece.title} is not a video piece")
    return piece


def _teleprompter(piece: Piece, folder: Path) -> tuple[list[dict], list[str]]:
    """What is said when, from the frames as they are saved now; or what stops reading them."""
    if not files.exists(folder, piece.type.main_file):
        return [], [f"{piece.type.main_file} has not been written yet."]
    text, _ = files.read(folder, piece.type.main_file)
    try:
        line = timing.timeline(frames.parse(text))
    except frames.FramesError as exc:
        return [], exc.problems
    return [{"title": scene.frame.title, "from": scene.start, "duration": scene.length,
             "speech": scene.speech, "script": " ".join(scene.frame.script.split())}
            for scene in line.scenes], []


def _page(request: Request, session: Session, piece: Piece, message: str = "",
          problems: list[str] | None = None) -> HTMLResponse:
    folder = workspace.piece_folder(session, piece)
    problems = list(problems or [])
    try:
        mix = voice.read_mix(folder)
    except voice.MixError as exc:
        mix, problems = voice.Mix(), [*problems, str(exc)]

    draft = assets.folder_of(folder) / renders.DRAFT_NAME
    frames_file = folder / piece.type.main_file
    scenes, frames_problems = _teleprompter(piece, folder)
    music = resources.listing(crud.brand_slug(session, piece.brand_id))["music"]
    takes = voice.takes(folder)
    # a file removed since it was chosen would otherwise just look unchosen, until a render fails
    if mix.take and mix.take not in {t.name for t in takes}:
        problems.append(f"The saved take, {mix.take}, is no longer in voice/. Choose another, or no voice, and save.")
    if mix.music and mix.music not in {m.name for m in music}:
        problems.append(f"The saved music, {mix.music}, is no longer in the brand's library. Choose again and save.")
    context = page_context(request, session, "pieces", piece.brand_id) | {
        "piece": piece,
        "message": message,
        "problems": problems,
        "frames_problems": frames_problems,
        "mix": mix,
        "takes": takes,
        "music": music,
        "has_draft": draft.is_file(),
        # the draft's timings are the frames' as they were when it was rendered
        "draft_stale": draft.is_file() and frames_file.is_file()
                       and frames_file.stat().st_mtime > draft.stat().st_mtime,
        # a browser records only on a secure address, which over http means loopback
        "can_record": opened_at_loopback(request),
        "record_url": str(request.url.replace(hostname="localhost", query="")),
        # what voice.js needs, handed over as JSON
        "studio": {
            "fps": FPS,
            "scenes": scenes,
            "draftUrl": f"/pieces/{piece.id}/assets/{renders.DRAFT_NAME}",
            "takeUrls": {t.name: f"/pieces/{piece.id}/voice/takes/{t.name}" for t in takes},
            "musicUrls": {m.name: f"/manage/brands/{piece.brand_id}/resources/music/{m.name}" for m in music},
            "uploadUrl": f"/pieces/{piece.id}/voice/takes",
        },
    }
    return templates.TemplateResponse(request, "voice.html", context)
