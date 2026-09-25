"""A brand's resources on its Manage page: uploading music and images, serving them, and
moving them to the trash. The panel answers every change by redrawing itself."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ... import assets, crud, desktop, files, resources
from ...database import get_session
from ...models import Brand
from ..local import from_this_machine
from ..serving import stored_file
from . import page

router = APIRouter(prefix="/brands/{brand_id}/resources")


def panel_context(request: Request, brand: Brand) -> dict:
    """What the Resources panel needs; the brand page uses it for its first render too."""
    return {
        "resources": resources.listing(brand.slug),
        "resources_folder": resources.brand_folder(brand.slug),
        "kit_folder": resources.kit_folder(brand.slug),
        "resources_accepted": ",".join(sorted(s for limits in resources.KINDS.values() for s in limits)),
        # a folder opened on the server is only seen by someone sitting at it
        "can_open_folder": from_this_machine(request),
    }


@router.post("", response_class=HTMLResponse)
def upload(brand_id: int, request: Request, uploads: list[UploadFile] = File(...),
           session: Session = Depends(get_session)):
    """Files dropped on the panel. Each goes to the folder its type belongs to, or is
    refused on its own, so one wrong file does not stop the rest."""
    brand = _brand(session, brand_id)
    stored, refused = [], []
    for upload_file in uploads:
        try:
            kind, name = resources.save(brand.slug, upload_file.filename or "", upload_file.file)
            stored.append(f"{kind}/{name}")
        except assets.BadAsset as exc:
            refused.append(str(exc))
    return _panel(request, brand, message=f"Added {', '.join(stored)}." if stored else "", problems=refused)


@router.get("/{kind}/{name}")
def serve(brand_id: int, kind: str, name: str, session: Session = Depends(get_session)):
    brand = _brand(session, brand_id)
    try:
        path = resources.path_of(brand.slug, kind, name)
    except (resources.UnknownKind, files.UnsafePath, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    return stored_file(path)


@router.post("/{kind}/{name}/delete", response_class=HTMLResponse)
def trash(brand_id: int, kind: str, name: str, request: Request, session: Session = Depends(get_session)):
    brand = _brand(session, brand_id)
    try:
        resources.trash(brand.slug, kind, name)
    except (resources.UnknownKind, files.UnsafePath, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    return _panel(request, brand, message=f"Moved {kind}/{name} to trash/{brand.slug}/resources/{kind}/.")


@router.post("/open", response_class=HTMLResponse)
def open_folder(brand_id: int, request: Request, session: Session = Depends(get_session)):
    """Open the brand's resources folder in this computer's file manager, when asked from it."""
    brand = _brand(session, brand_id)
    if not from_this_machine(request):
        return _panel(request, brand, problems=["The folder can only be opened on the machine running the app."])
    try:
        desktop.open_folder(resources.brand_folder(brand.slug))
    except desktop.DesktopError as exc:
        return _panel(request, brand, problems=[str(exc)])
    return _panel(request, brand, message="Opened the folder.")


def _brand(session: Session, brand_id: int) -> Brand:
    brand = crud.get_brand(session, brand_id)
    if not brand:
        raise HTTPException(404, "brand not found")
    return brand


def _panel(request: Request, brand: Brand, message: str = "", problems: list[str] | None = None) -> HTMLResponse:
    return page.partial(request, "manage/resources_panel.html", brand=brand, message=message,
                        problems=problems or [], **panel_context(request, brand))
