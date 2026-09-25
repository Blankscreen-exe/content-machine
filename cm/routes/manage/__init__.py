"""The Manage tab: brands and the lists you pick from elsewhere, one module per section."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from . import brands, modes, platforms, resources, types

router = APIRouter(prefix="/manage")


@router.get("")
def manage_home() -> RedirectResponse:
    return RedirectResponse("/manage/brands", status_code=303)


router.include_router(brands.router)
router.include_router(resources.router)
router.include_router(modes.router)
router.include_router(types.router)
router.include_router(platforms.router)
