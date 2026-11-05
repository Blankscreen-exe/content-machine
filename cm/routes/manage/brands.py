"""Brands: add, rename, turn off, and each one's page: its voice and profile, its modes,
its cadence and its resources.

The voice and profile live in the database and are handed to sessions in brief.md. They
are edited in the same pane as drafts, with the same check that nothing changed them —
another tab, most likely — since they were opened. Adding and renaming open in the dialog.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ... import choices, crud, scaffold
from ...database import get_session
from ...files import digest
from ...models import Brand, Mode
from . import cadences, modes, page, resources

router = APIRouter(prefix="/brands")

# The two texts a brand has, and the tab each one gets.
Text = Literal["voice", "profile"]
TEXT_LABELS = {"voice": "Voice", "profile": "Brand profile"}

# Where a change to a brand was made: the list of brands, or the brand's own page, which
# decides what the answer redraws.
Origin = Literal["list", "page"]


@router.get("", response_class=HTMLResponse)
def brands(request: Request, session: Session = Depends(get_session)):
    return page.render(request, session, "brands", "manage/brands.html", **_list_context(session))


@router.get("/new", response_class=HTMLResponse)
def brand_new(request: Request):
    """The form for a new brand, opened in the dialog."""
    return page.partial(request, "manage/brand_form.html", brand=None)


@router.post("", response_class=HTMLResponse)
def brand_create(request: Request, slug: str = Form(...), name: str = Form(""),
                 session: Session = Depends(get_session)):
    name = name.strip() or slug.strip()
    crud.create_brand(session, slug, name, **scaffold.brand_starter(name))
    return _list(request, session)


@router.get("/{brand_id}/rename", response_class=HTMLResponse)
def brand_rename_form(brand_id: int, request: Request, session: Session = Depends(get_session)):
    """Renaming, opened in the dialog from the brand's page."""
    return page.partial(request, "manage/brand_form.html", brand=_brand(session, brand_id))


@router.post("/{brand_id}", response_class=HTMLResponse)
def brand_rename(brand_id: int, request: Request, name: str = Form(...),
                 session: Session = Depends(get_session)):
    """Only the name: the slug names the brand's folders, so it never changes. Renaming is
    done from the brand's page, so it redraws that page's heading."""
    brand = _brand(session, brand_id)
    crud.update_brand(session, brand, name=" ".join(name.split()))
    return page.partial(request, "manage/brand_head.html", brand=brand)


@router.post("/{brand_id}/active", response_class=HTMLResponse)
def brand_active(brand_id: int, request: Request, active: bool = Form(...),
                 origin: Origin = Form("list"), session: Session = Depends(get_session)):
    """Turning a brand off hides it from the filters; its ideas and pieces stay."""
    brand = _brand(session, brand_id)
    crud.update_brand(session, brand, active=active)
    if origin == "page":
        return page.partial(request, "manage/brand_head.html", brand=brand)
    return _list(request, session)


@router.get("/{brand_id}", response_class=HTMLResponse)
def brand_page(brand_id: int, request: Request, session: Session = Depends(get_session)):
    brand = _brand(session, brand_id)
    return page.render(request, session, "brands", "manage/brand.html", brand=brand,
                       **_pane(brand, "voice", brand.voice), **modes.panel_context(session, brand.id),
                       **cadences.panel_context(session, brand), **resources.panel_context(request, brand))


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


def _list_context(session: Session) -> dict:
    """Every brand, with how many modes and pieces each has, as the list shows them."""
    brands = crud.list_brands(session)
    return {
        "brands": brands,
        "mode_counts": {b.id: len(choices.all_items(session, Mode, brand_id=b.id)) for b in brands},
        "piece_counts": {b.id: crud.piece_counts(session, b.id)["total"] for b in brands},
    }


def _list(request: Request, session: Session) -> HTMLResponse:
    return page.partial(request, "manage/brand_list.html", **_list_context(session))


def _pane(brand: Brand, field: str, text: str, fingerprint: str | None = None,
          message: str = "", conflict: bool = False) -> dict:
    """The editor pane pointed at one of a brand's texts, saying above it what they are for.
    No image uploads: a brand has no folder of its own for them."""
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
        "intro": "Both go to every session for this brand, in brief.md: the voice is how the "
                 "brand writes, the profile its identity and visual constants.",
    }}
