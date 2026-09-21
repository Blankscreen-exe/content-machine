"""Template setup and the context every page needs."""
from __future__ import annotations

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from . import crud
from .models import IdeaStatus, PieceType, Stage
from .paths import TEMPLATES_DIR, THEMES_DIR
from .terminals import available_terminals

templates = Jinja2Templates(directory=TEMPLATES_DIR)

STATUSES = [s.value for s in IdeaStatus]
STAGES = [s.value for s in Stage]
TYPES = [t.value for t in PieceType]


def page_context(request: Request, session: Session, view: str, brand_id: int | None) -> dict:
    """Shared by every full page render: brands, theme, which tab is active."""
    return {
        "request": request,
        "view": view,
        "base": "/" if view == "ideas" else f"/{view}",
        "brand_id": brand_id,
        "brands": crud.list_brands(session),
        "settings": crud.get_settings_map(session),
        "themes": sorted(p.stem for p in THEMES_DIR.glob("*.css")),
        "terminals": available_terminals(),
        "statuses": STATUSES,
        "stages": STAGES,
        "types": TYPES,
    }
