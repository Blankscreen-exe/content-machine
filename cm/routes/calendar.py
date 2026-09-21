"""The Calendar tab: what is due, and a month of pieces laid out by due date."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .. import crud, month
from ..database import get_session
from ..templating import page_context, templates
from .params import OptionalId

router = APIRouter(prefix="/calendar")


@router.get("", response_class=HTMLResponse)
def calendar_page(request: Request, session: Session = Depends(get_session),
                  brand_id: OptionalId = None,
                  shown: str | None = Query(None, alias="month", description="YYYY-MM")):
    """One month, this one unless the address names another."""
    today = date.today()
    grid = month.grid(month.parse(shown, today), today)
    month.place(grid, crud.pieces_due_between(session, grid.start, grid.end, brand_id))

    context = page_context(request, session, "calendar", brand_id)
    context |= {
        "month": grid,
        "weekdays": month.WEEKDAY_NAMES,
        "today": today,
        "undated": crud.undated_count(session, brand_id),
    }
    return templates.TemplateResponse(request, "calendar.html", context)
