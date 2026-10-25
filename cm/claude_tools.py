"""What a Claude session may do to the database: its tools, as plain functions over crud.

mcp_server.py hands these to Claude. Nothing here knows about MCP, so the rules can be read
and tested on their own. A set of tools is bound to one brand: a piece or idea of another
brand is "not found", so a session cannot read or file work under a brand it was not
opened for. Every change is recorded as Claude's.

What is missing is the point. Nothing here moves a piece to ready (that is your proofread)
or published, records a publication, deletes anything, or touches a brand's voice,
profile or modes, the settings or the managed lists. Those stay yours, in the app.

The docstrings are what Claude reads about each tool, so they are written to it.
"""
from __future__ import annotations

import html
import shutil
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session

from . import cadence, choices, crud, frames, renders, resources, search, video, workspace
from .models import PRIORITIES, Actor, Idea, IdeaStatus, Mode, Piece, PieceType, Stage
from .settings import get_settings

# Where Claude may move a piece, and the stages it may move one from. Past wip is yours.
CLAUDE_STAGES = (Stage.draft, Stage.wip)
MOVABLE_STAGES = (Stage.not_started, Stage.draft, Stage.wip)
# An idea goes back to the pool or on into pieces; parking or dropping one is your call.
CLAUDE_STATUSES = (IdeaStatus.pool, IdeaStatus.promoted)
# Enough dates for a few months of daily posts; more is a mistake, not a plan.
MOST_SLOTS = 100


class Refused(Exception):
    """A tool would not do what was asked; the message says why, and what to do instead."""


class Tools:
    """The tools for one brand's session. Each call opens its own database session, so it
    sees what the app wrote a moment ago."""

    def __init__(self, engine: Engine, brand_slug: str) -> None:
        self._engine = engine
        with Session(engine) as session:
            brand = crud.get_brand_by_slug(session, brand_slug)
            if not brand:
                raise Refused(f"There is no brand with the slug {brand_slug!r}. The slugs are on the "
                              "Manage page in the app.")
            self.brand_id, self.brand_slug = brand.id, brand.slug

    def all(self) -> list[Callable]:
        """Every tool that answers with data, in the order Claude sees them. `still` answers
        with a picture, so the server adds it on its own."""
        return [self.brand_context, self.list_piece_types,
                self.list_ideas, self.get_idea, self.create_idea, self.update_idea,
                self.list_pieces, self.get_piece, self.create_piece, self.update_piece, self.next_slots,
                self.set_stage, self.add_note, self.search_drafts,
                self.start_kit, self.render_draft]

    # --- the brand ---------------------------------------------------------------------------

    def brand_context(self) -> dict:
        """The brand this session writes for: its voice, its profile and the modes it writes
        in. Read it before writing anything new."""
        with self._session() as session:
            brand = crud.get_brand(session, self.brand_id)
            modes = choices.options(session, Mode, brand_id=self.brand_id)
            return {"name": brand.name, "slug": brand.slug, "voice": brand.voice, "profile": brand.profile,
                    "modes": [{"name": mode.name, "description": mode.description} for mode in modes]}

    def list_piece_types(self) -> list[dict]:
        """The kinds of piece there are, each with the file its draft goes in and any
        character limit."""
        with self._session() as session:
            return [{"name": kind.name, "main_file": kind.main_file, "char_limit": kind.char_limit,
                     "video": kind.video} for kind in choices.options(session, PieceType)]

    # --- ideas -------------------------------------------------------------------------------

    def list_ideas(self, status: IdeaStatus | None = None) -> list[dict]:
        """This brand's ideas, highest priority first, optionally only those with one status."""
        with self._session() as session:
            return [_idea(idea) for idea in crud.list_ideas(session, brand_id=self.brand_id, status=status)]

    def get_idea(self, idea_id: int) -> dict:
        """One idea, in full."""
        with self._session() as session:
            return _idea(self._idea(session, idea_id))

    def create_idea(self, title: str, angle: str = "", talking_points: str = "", source: str = "",
                    mode: str | None = None, priority: str = "normal") -> dict:
        """Add an idea to the pool. `mode` is one of the brand's modes by name; `priority` is
        high, normal or low; `source` is where the idea came from."""
        with self._session() as session:
            idea = crud.create_idea(session, brand_id=self.brand_id, title=_title(title), angle=angle,
                                    talking_points=talking_points, source=source,
                                    mode_id=self._mode_id(session, mode), priority=_priority(priority))
            return _idea(idea)

    def update_idea(self, idea_id: int, title: str | None = None, angle: str | None = None,
                    talking_points: str | None = None, source: str | None = None, notes: str | None = None,
                    mode: str | None = None, priority: str | None = None,
                    status: IdeaStatus | None = None) -> dict:
        """Change an idea. Only what is given changes. `status` may be pool or promoted;
        parking or dropping an idea is for me to decide."""
        if status is not None and status not in CLAUDE_STATUSES:
            raise Refused(f"An idea can be moved to {' or '.join(s.value for s in CLAUDE_STATUSES)} here. "
                          f"Moving one to {status.value} is mine to decide: tell me why you would.")
        with self._session() as session:
            idea = self._idea(session, idea_id)
            fields = {"title": _title(title) if title is not None else None, "angle": angle,
                      "talking_points": talking_points, "source": source, "notes": notes, "status": status,
                      "mode_id": self._mode_id(session, mode) if mode is not None else None,
                      "priority": _priority(priority) if priority is not None else None}
            return _idea(crud.update_idea(session, idea, **_given(fields)))

    # --- pieces ------------------------------------------------------------------------------

    def list_pieces(self, stage: Stage | None = None, type: str | None = None) -> list[dict]:
        """This brand's pieces, soonest due first, optionally only one stage or one type."""
        with self._session() as session:
            type_id = self._type(session, type).id if type else None
            pieces = crud.list_pieces(session, brand_id=self.brand_id, stage=stage, type_id=type_id)
            return [_piece(session, piece) for piece in pieces]

    def get_piece(self, piece_id: int) -> dict:
        """One piece, with the folder its files are in."""
        with self._session() as session:
            return _piece(session, self._piece(session, piece_id))

    def create_piece(self, type: str, title: str, idea_id: int | None = None,
                     source_piece_id: int | None = None, due_on: date | None = None) -> dict:
        """File a new piece and make its folder, with a brief.md in it. Write its draft into
        that folder, in the type's main file. `source_piece_id` is the piece it is made
        from, such as the blog post a LinkedIn post repackages."""
        with self._session() as session:
            kind = self._type(session, type)
            if idea_id is not None:
                self._idea(session, idea_id)
            if source_piece_id is not None:
                self._piece(session, source_piece_id)
            piece = crud.create_piece(session, brand_id=self.brand_id, type_id=kind.id, title=_title(title),
                                      idea_id=idea_id, source_piece_id=source_piece_id, due_on=due_on)
            workspace.write_brief(session, piece)
            return _piece(session, piece)

    def update_piece(self, piece_id: int, title: str | None = None, due_on: date | None = None) -> dict:
        """Change a piece's title or due date. Only what is given changes. Its stage has
        set_stage, its notes add_note."""
        with self._session() as session:
            piece = self._piece(session, piece_id)
            fields = {"title": _title(title) if title is not None else None, "due_on": due_on}
            return _piece(session, crud.update_piece(session, piece, **_given(fields)))

    def next_slots(self, type: str, count: int, start: date | None = None) -> list[str]:
        """The next `count` free due dates for a piece type, by the brand's cadence for it,
        from `start` (today if not given). Give each new piece of the type one of them, in
        order, as its due_on."""
        if not 1 <= count <= MOST_SLOTS:
            raise Refused(f"Ask for 1 to {MOST_SLOTS} dates at a time.")
        with self._session() as session:
            kind = self._type(session, type)
            days = crud.next_slots(session, self.brand_id, kind.id, count, start or date.today())
            return [day.isoformat() for day in days]

    def set_stage(self, piece_id: int, stage: Stage) -> dict:
        """Move a piece to draft (a first version is written) or wip (being reworked). Ready
        and published are mine: I move a piece there once I have proofread or posted it."""
        if stage not in CLAUDE_STAGES:
            raise Refused(f"A piece can be moved to {' or '.join(s.value for s in CLAUDE_STAGES)} here. "
                          f"{stage.value.capitalize()} is mine: I move a piece there after proofreading "
                          "or posting it. Tell me it is waiting for me instead.")
        with self._session() as session:
            piece = self._piece(session, piece_id)
            if piece.stage not in MOVABLE_STAGES:
                raise Refused(f"{piece.title} is {piece.stage.value}, past where you can move it. "
                              "Tell me what you would change and why.")
            return _piece(session, crud.update_piece(session, piece, stage=stage))

    def add_note(self, piece_id: int, text: str) -> dict:
        """Add a line to a piece's notes, such as what you did or what is still open. The
        notes keep everything written before."""
        if not text.strip():
            raise Refused("The note is empty. Say what you did or what is still open.")
        with self._session() as session:
            piece = self._piece(session, piece_id)
            notes = f"{piece.notes}\n{text.strip()}".strip()
            return _piece(session, crud.update_piece(session, piece, notes=notes))

    def search_drafts(self, query: str) -> list[dict]:
        """The brand's pieces whose drafts contain every word of `query`, best match first,
        each with a few words either side of where it matched (matches in **bold**)."""
        with self._session() as session:
            return [{"piece_id": hit.piece.id, "title": hit.piece.title, "file": hit.name,
                     "snippet": html.unescape(hit.snippet.replace("<mark>", "**").replace("</mark>", "**"))}
                    for hit in search.search(session, query, brand_id=self.brand_id)]

    # --- video -------------------------------------------------------------------------------

    def start_kit(self) -> dict:
        """Copy the example kit into this brand's kit folder, to restyle. Only once I have
        said yes, and only when the brand has no kit yet."""
        kit = resources.kit_folder(self.brand_slug)
        if kit.exists():
            raise Refused(f"The brand already has a kit, at {kit}. Restyle that one.")
        example = get_settings().workspace / "video" / "example-kit"
        if not example.is_dir():
            raise Refused(f"The example kit is missing from {example}. Ask me to run `cm init`.")
        shutil.copytree(example, kit)
        return {"kit": str(kit)}

    def render_draft(self, piece_id: int) -> dict:
        """Render a video piece as a quick half-size draft, to assets/draft.mp4. Takes a minute
        or more. Look at it afterwards with still. Never a final: that waits for my voice."""
        with self._session() as session:
            piece = self._piece(session, piece_id)
            try:
                path = renders.render_piece(session, piece, draft=True)
            except frames.FramesError as exc:
                raise Refused(f"{piece.type.main_file} needs fixing first:\n- " + "\n- ".join(exc.problems)) from exc
            except video.RenderError as exc:
                raise Refused(str(exc)) from exc
            return {"draft": str(path)}

    def still(self, piece_id: int, seconds: float) -> bytes:
        """The frame of a piece's draft render at `seconds`, as a PNG, to look at. Take one
        from the middle of each scene (seconds = frame / 30)."""
        with self._session() as session:
            piece = self._piece(session, piece_id)
            draft = workspace.piece_folder(session, piece) / "assets" / renders.DRAFT_NAME
        if not draft.is_file():
            raise Refused(f"{piece.title} has no draft render yet. Run render_draft first.")
        with tempfile.TemporaryDirectory() as scratch:      # nothing left behind to clean up
            try:
                return video.still(get_settings().workspace, draft, seconds, Path(scratch) / "still.png").read_bytes()
            except video.RenderError as exc:
                raise Refused(str(exc)) from exc

    # --- lookups, always inside this brand ---------------------------------------------------

    @contextmanager
    def _session(self):
        with Session(self._engine) as session:
            crud.act_as(session, Actor.claude)
            try:
                yield session
            except (crud.ChoiceError, cadence.BadRule) as exc:
                # crud's own refusals: a mode of another brand, a type with no cadence
                raise Refused(str(exc)) from exc

    def _piece(self, session: Session, piece_id: int) -> Piece:
        piece = crud.get_piece(session, piece_id)
        if not piece or piece.brand_id != self.brand_id:     # one message, so other brands stay unseen
            raise Refused(f"There is no piece {piece_id} in {self.brand_slug}. list_pieces shows them.")
        return piece

    def _idea(self, session: Session, idea_id: int) -> Idea:
        idea = crud.get_idea(session, idea_id)
        if not idea or idea.brand_id != self.brand_id:
            raise Refused(f"There is no idea {idea_id} in {self.brand_slug}. list_ideas shows them.")
        return idea

    def _type(self, session: Session, name: str) -> PieceType:
        kind = choices.by_name(session, PieceType, name)
        if not kind or not kind.active:
            known = ", ".join(k.name for k in choices.options(session, PieceType))
            raise Refused(f"There is no piece type called {name!r}. The types are: {known}. "
                          "A new type is added by me, on the Manage page.")
        return kind

    def _mode_id(self, session: Session, name: str | None) -> int | None:
        if not name:
            return None
        mode = choices.by_name(session, Mode, name, brand_id=self.brand_id)
        if not mode or not mode.active:
            known = ", ".join(m.name for m in choices.options(session, Mode, brand_id=self.brand_id)) or "none yet"
            raise Refused(f"{self.brand_slug} has no mode called {name!r}. Its modes are: {known}.")
        return mode.id


def _given(fields: dict) -> dict:
    """The fields a call actually gave; None means leave as it is."""
    return {key: value for key, value in fields.items() if value is not None}


def _title(title: str) -> str:
    if not title.strip():
        raise Refused("A title cannot be empty.")
    return title.strip()


def _priority(name: str) -> int:
    for number, label in PRIORITIES.items():
        if label == name.strip().lower():
            return number
    raise Refused(f"Priority is one of: {', '.join(PRIORITIES.values())}.")


def _idea(idea: Idea) -> dict:
    return {"id": idea.id, "title": idea.title, "angle": idea.angle, "talking_points": idea.talking_points,
            "notes": idea.notes, "source": idea.source, "mode": idea.mode.name if idea.mode else None,
            "status": idea.status.value, "priority": PRIORITIES.get(idea.priority, str(idea.priority))}


def _piece(session: Session, piece: Piece) -> dict:
    return {"id": piece.id, "title": piece.title, "type": piece.type.name, "stage": piece.stage.value,
            "due_on": piece.due_on.isoformat() if piece.due_on else None, "idea_id": piece.idea_id,
            "source_piece_id": piece.source_piece_id, "notes": piece.notes,
            "folder": str(workspace.piece_folder(session, piece)), "main_file": piece.type.main_file}
