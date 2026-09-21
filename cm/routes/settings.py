"""Settings: preferences — appearance, terminal, reminders — and where the workspace is.

Brands and the lists you pick from are data, not preferences; they live under Manage.
"""
from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from .. import crud
from ..database import get_session
from ..settings import get_settings
from ..templating import page_context, templates

router = APIRouter()


def _whole_days(value: str) -> str:
    days = int(value)          # a ValueError here becomes the message below
    if not 0 <= days <= 365:
        raise ValueError
    return str(days)


# Only these can be written from the browser, so a stray form cannot invent a setting.
# Each one maps to the check its value must pass, which returns the value to store.
ALLOWED_SETTINGS = {
    "theme": str.strip,
    "terminal": str.strip,
    "due_soon_days": _whole_days,
}
SETTING_RULES = {"due_soon_days": "a whole number of days from 0 to 365"}


@router.get("/settings", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    context = page_context(request, session, "settings", brand_id=None)
    context |= {
        "paths": get_settings(),
        "claude_installed": bool(shutil.which("claude")),
    }
    return templates.TemplateResponse(request, "settings.html", context)


@router.post("/settings", response_class=HTMLResponse)
def setting_set(key: str = Form(...), value: str = Form(...),
                session: Session = Depends(get_session)):
    """Store a preference. A theme change needs the page reloaded; others do not."""
    if key not in ALLOWED_SETTINGS:
        raise HTTPException(400, f"unknown setting {key!r}")
    try:
        value = ALLOWED_SETTINGS[key](value)
    except ValueError:
        raise HTTPException(400, f"{key} must be {SETTING_RULES[key]}") from None
    crud.set_setting(session, key, value)
    return Response(status_code=204, headers={"HX-Refresh": "true"} if key == "theme" else {})

