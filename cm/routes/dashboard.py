"""The Dashboard: the page you land on, answering "what do I pick up now?"

Four short lists, each linking through: what is due today or overdue, what is in progress,
the ideas to start next, and what went out last. All follow the brand filter.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .. import crud
from ..database import get_session
from ..templating import page_context, templates
from .params import OptionalId

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session), brand_id: OptionalId = None):
    today = date.today()
    context = page_context(request, session, "dashboard", brand_id)
    due = context["due"]
    context |= {
        "today": today,
        # the Calendar tab lists the whole window; here only what needs doing now
        "due_now": due.overdue + [piece for piece in due.soon if piece.due_on == today],
        "in_progress": crud.pieces_in_progress(session, brand_id),
        "next_ideas": crud.top_pool_ideas(session, brand_id),
        "published": crud.recent_publications(session, brand_id),
    }
    return templates.TemplateResponse(request, "dashboard.html", context)
