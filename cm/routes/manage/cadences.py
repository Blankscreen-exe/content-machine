"""A brand's cadences on its Manage page: how often it publishes each piece type. The panel
answers every change by redrawing itself."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ... import cadence, choices, crud
from ...database import get_session
from ...models import Brand, CadenceRule, PieceType
from . import page

router = APIRouter(prefix="/brands/{brand_id}/cadence")

# What each rule is called in the form; the number or day it needs sits beside it.
RULE_LABELS = {CadenceRule.weekdays: "every weekday", CadenceRule.every_n_days: "every N days",
               CadenceRule.weekly: "weekly on"}


def panel_context(session: Session, brand: Brand) -> dict:
    """What the Cadence panel needs; the brand page uses it for its first render too. Every
    piece type in use, and any turned off that still has a cadence here."""
    cadences = crud.list_cadences(session, brand.id)
    kinds = [kind for kind in choices.all_items(session, PieceType) if kind.active or kind.id in cadences]
    return {
        "cadence_rows": [(kind, cadence.Rule.of(cadences[kind.id]) if kind.id in cadences else None)
                         for kind in kinds],
        "rule_labels": RULE_LABELS,
        "weekdays": cadence.WEEKDAYS,
    }


@router.post("/{type_id}", response_class=HTMLResponse)
def cadence_set(brand_id: int, type_id: int, request: Request, rule: str = Form(""),
                every_days: str = Form(""), weekday: str = Form(""),
                session: Session = Depends(get_session)):
    """`rule` empty means no rhythm for the type. The number and the day come as text, as
    a form sends a field left empty."""
    brand = _brand(session, brand_id)
    kind = page.item_or_404(session, PieceType, type_id)
    try:
        chosen = cadence.from_form(CadenceRule(rule), _number(every_days), _number(weekday)) if rule else None
    except ValueError as exc:                   # a BadRule, or a rule the form never offers
        return _panel(request, session, brand, problem=f"{kind.name}: {exc}")
    crud.set_cadence(session, brand.id, kind.id, chosen)
    return _panel(request, session, brand, message=f"{kind.name}: {chosen.describe() if chosen else 'no rhythm'}.")


def _number(text: str) -> int | None:
    text = text.strip()
    if text and not text.isdigit():
        raise cadence.BadRule(f"{text!r} is not a whole number.")
    return int(text) if text else None


def _brand(session: Session, brand_id: int) -> Brand:
    brand = crud.get_brand(session, brand_id)
    if not brand:
        raise HTTPException(404, "brand not found")
    return brand


def _panel(request: Request, session: Session, brand: Brand, message: str = "",
           problem: str = "") -> HTMLResponse:
    return page.partial(request, "manage/cadence_panel.html", brand=brand, message=message, problem=problem,
                        **panel_context(session, brand))
