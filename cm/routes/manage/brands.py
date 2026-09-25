"""Brands: add, rename, turn off, and write each one's voice and profile.

The voice and profile live in the database and are handed to sessions in brief.md. They
are edited in the same pane as drafts, with the same check that nothing changed them —
another tab, most likely — since they were opened.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ... import crud, scaffold
from ...database import get_session
from ...files import digest
from ...models import Brand
from . import page, resources

router = APIRouter(prefix="/brands")

# The two texts a brand has, and the tab each one gets.
Text = Literal["voice", "profile"]
TEXT_LABELS = {"voice": "Voice", "profile": "Brand profile"}


@router.get("", response_class=HTMLResponse)
def brands(request: Request, session: Session = Depends(get_session)):
    return page.render(request, session, "brands", "manage/brands.html",
                       brands=crud.list_brands(session))


@router.post("", response_class=HTMLResponse)
def brand_create(request: Request, slug: str = Form(...), name: str = Form(""),
                 session: Session = Depends(get_session)):
    name = name.strip() or slug.strip()
    crud.create_brand(session, slug, name, **scaffold.brand_starter(name))
    return _list(request, session)


@router.post("/{brand_id}", response_class=HTMLResponse)
def brand_rename(brand_id: int, request: Request, name: str = Form(...),
                 session: Session = Depends(get_session)):
    """Only the name: the slug names the brand's folders, so it never changes."""
    crud.update_brand(session, _brand(session, brand_id), name=" ".join(name.split()))
    return _list(request, session)


@router.post("/{brand_id}/active", response_class=HTMLResponse)
def brand_active(brand_id: int, request: Request, active: bool = Form(...),
                 session: Session = Depends(get_session)):
    """Turning a brand off hides it from the filters; its ideas and pieces stay."""
    crud.update_brand(session, _brand(session, brand_id), active=active)
    return _list(request, session)


@router.get("/{brand_id}", response_class=HTMLResponse)
def brand_page(brand_id: int, request: Request, session: Session = Depends(get_session)):
    brand = _brand(session, brand_id)
    return page.render(request, session, "brands", "manage/brand.html", brand=brand,
                       **_pane(brand, "voice", brand.voice), **resources.panel_context(request, brand))


@router.get("/{brand_id}/text/{field}", response_class=HTMLResponse)
def text_open(brand_id: int, field: Text, request: Request,
              session: Session = Depends(get_session)):
    brand = _brand(session, brand_id)
    return page.partial(request, "partials/editor_pane.html",
                        **_pane(brand, field, getattr(brand, field)))


@router.post("/{brand_id}/text/{field}", response_class=HTMLResponse)
def text_save(brand_id: int, field: Text, request: Request, text: str = Form(""),
              fingerprint: str = Form(""), force: bool = Form(False),
              session: Session = Depends(get_session)):
    brand = _brand(session, brand_id)
    saved = getattr(brand, field)
    if not force and digest(saved) != fingerprint:
        # Keep what was typed on screen; offer to reload or to overwrite deliberately.
        return page.partial(request, "partials/editor_pane.html",
                            **_pane(brand, field, text, fingerprint=digest(saved), conflict=True,
                                    message="This was changed somewhere else since you opened it."))
    crud.update_brand(session, brand, **{field: text})
    return page.partial(request, "partials/editor_pane.html",
                        **_pane(brand, field, text, message="Saved"))


def _brand(session: Session, brand_id: int) -> Brand:
    brand = crud.get_brand(session, brand_id)
    if not brand:
        raise HTTPException(404, "brand not found")
    return brand


def _list(request: Request, session: Session) -> HTMLResponse:
    return page.partial(request, "manage/brand_list.html", brands=crud.list_brands(session))


def _pane(brand: Brand, field: str, text: str, fingerprint: str | None = None,
          message: str = "", conflict: bool = False) -> dict:
    """The editor pane pointed at one of a brand's texts. No image uploads: a brand has no
    folder of its own for them."""
    base = f"/manage/brands/{brand.id}/text"
    return {"pane": {
        "tabs": [{"label": label, "url": f"{base}/{name}", "on": name == field}
                 for name, label in TEXT_LABELS.items()],
        "save_url": f"{base}/{field}",
        "open_url": f"{base}/{field}",
        "text": text,
        "fingerprint": fingerprint or digest(text),
        "editable": True,
        "count_characters": True,
        "message": message,
        "conflict": conflict,
    }}
