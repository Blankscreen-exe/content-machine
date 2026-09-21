"""All page routes, behind the access token."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..security import require_token
from . import assets, editor, ideas, pieces, publications, settings

router = APIRouter(dependencies=[Depends(require_token)])
router.include_router(ideas.router)
router.include_router(pieces.router)
router.include_router(publications.router)
router.include_router(editor.router)
router.include_router(assets.router)
router.include_router(settings.router)
