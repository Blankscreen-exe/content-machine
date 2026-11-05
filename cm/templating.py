"""Template setup and the context every page needs."""
from __future__ import annotations

from datetime import date

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from . import crud, schedule, themes
from .dates import local_date, local_time
from .models import PRIORITIES, IdeaStatus, Stage
from .paths import TEMPLATES_DIR
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


def filesize(size: int) -> str:
    """1536 -> '1.5 KB'. Binary units, as file managers show them; assets stay under a GB."""
    if size < 1024:
        return f"{size} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# Available in every template without being passed in each context.
templates.env.filters["status_class"] = status_class
templates.env.filters["priority_name"] = priority_name
templates.env.filters["filesize"] = filesize
templates.env.filters["local_date"] = lambda moment: local_date(moment).isoformat()
templates.env.filters["local_time"] = lambda moment: local_time(moment).strftime("%Y-%m-%d %H:%M")
templates.env.globals["priorities"] = PRIORITIES
# one rule for "overdue" wherever a piece is shown, so the list, the calendar and the piece agree
templates.env.globals["is_late"] = lambda piece: schedule.is_late(piece, date.today())


def page_context(request: Request, session: Session, view: str, brand_id: int | None) -> dict:
    """Shared by every full page render: brands, theme, which tab is active."""
    return {
        "request": request,
        "view": view,
        "base": "/" if view == "dashboard" else f"/{view}",     # where the brand filter reloads
        "brand_id": brand_id,
        "brands": crud.list_brands(session),
        "settings": _settings(session),
        "themes": themes.available(),
        "terminals": available_terminals(),
        "statuses": STATUSES,
        "stages": STAGES,
        "due": schedule.due(session, date.today(), brand_id),
    }


def _settings(session: Session) -> dict[str, str]:
    """The stored settings, with the theme one a page can actually load."""
    settings = crud.get_settings_map(session)
    settings["theme"] = themes.resolve(settings["theme"])
    return settings
