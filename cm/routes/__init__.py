"""All page routes, behind the access token."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..security import require_token
from . import assets, calendar, dashboard, editor, ideas, manage, pieces, publications, render, settings

router = APIRouter(dependencies=[Depends(require_token)])
router.include_router(dashboard.router)
router.include_router(ideas.router)
router.include_router(pieces.router)
router.include_router(publications.router)
router.include_router(calendar.router)
router.include_router(editor.router)
router.include_router(assets.router)
router.include_router(render.router)
router.include_router(manage.router)
router.include_router(settings.router)
