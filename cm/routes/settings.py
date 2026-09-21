"""Settings: appearance, terminal, and the brands you write for."""
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

# Only these can be written from the browser, so a stray form cannot invent a setting.
ALLOWED_SETTINGS = {"theme", "terminal"}


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
    crud.set_setting(session, key, value)
    return Response(status_code=204, headers={"HX-Refresh": "true"} if key == "theme" else {})


@router.post("/brands", response_class=HTMLResponse)
def brand_create(request: Request, slug: str = Form(...), name: str = Form(""),
                 session: Session = Depends(get_session)):
    crud.create_brand(session, slug.strip(), name.strip() or slug.strip())
    return _brand_list(request, session)


@router.post("/brands/{brand_id}", response_class=HTMLResponse)
def brand_update(brand_id: int, request: Request, name: str = Form(...),
                 session: Session = Depends(get_session)):
    brand = crud.get_brand(session, brand_id)
    if not brand:
        raise HTTPException(404, "brand not found")
    crud.update_brand(session, brand, name=name.strip())
    return _brand_list(request, session)


@router.post("/brands/{brand_id}/active", response_class=HTMLResponse)
def brand_active(brand_id: int, request: Request, active: bool = Form(...),
                 session: Session = Depends(get_session)):
    """Deactivating hides a brand from the filters; its ideas and pieces stay."""
    brand = crud.get_brand(session, brand_id)
    if not brand:
        raise HTTPException(404, "brand not found")
    crud.update_brand(session, brand, active=active)
    return _brand_list(request, session)


def _brand_list(request: Request, session: Session) -> HTMLResponse:
    return templates.TemplateResponse(request, "partials/brand_list.html",
                                      {"request": request, "brands": crud.list_brands(session)})
