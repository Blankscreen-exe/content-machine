"""Template setup and the context every page needs."""
from __future__ import annotations

from datetime import date

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from . import crud, schedule
from .dates import local_date
from .models import PRIORITIES, IdeaStatus, Stage
from .paths import TEMPLATES_DIR, THEMES_DIR
from .terminals import available_terminals
from .text import slugify

templates = Jinja2Templates(directory=TEMPLATES_DIR)

STATUSES = [s.value for s in IdeaStatus]
STAGES = [s.value for s in Stage]


def status_class(value: str) -> str:
    """The CSS class a theme colours a status or stage by: 'not started' -> 'status-not-started'."""
    return f"status-{slugify(value)}"


def priority_name(value: int) -> str:
    return PRIORITIES.get(value, str(value))


# Available in every template without being passed in each context.
templates.env.filters["status_class"] = status_class
templates.env.filters["priority_name"] = priority_name
templates.env.filters["local_date"] = lambda moment: local_date(moment).isoformat()
templates.env.globals["priorities"] = PRIORITIES


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
        "due": schedule.due(session, date.today(), brand_id),
    }
