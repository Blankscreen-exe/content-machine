"""What every Manage section shares: the sidebar, the page around it, and item lookups."""
from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ... import choices
from ...templating import page_context, templates

# The sidebar, in order: (address under /manage, label).
SECTIONS = [
    ("brands", "Brands"),
    ("modes", "Modes"),
    ("types", "Piece types"),
    ("platforms", "Platforms"),
]


def render(request: Request, session: Session, section: str, template: str,
           **context) -> HTMLResponse:
    """A full Manage page: the sidebar with `section` selected, and its template beside it."""
    page = page_context(request, session, "manage", brand_id=None)
    page |= {"sections": SECTIONS, "section": section, **context}
    return templates.TemplateResponse(request, template, page)


def partial(request: Request, template: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(request, template, {"request": request, **context})


def item_or_404(session: Session, kind: type[choices.Choice], item_id: int) -> choices.Choice:
    item = choices.get(session, kind, item_id)
    if not item:
        raise HTTPException(404, f"{kind.__name__.lower()} not found")
    return item
