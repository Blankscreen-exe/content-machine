"""FastAPI application factory."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .choices import ChoiceError
from .database import migrate
from .hangups import ignore_client_hangups
from .paths import STATIC_DIR
from .routes import router
from .routes.serving import AppFiles
from .security import remember_token


def _lifespan(run_migrations: bool):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ignore_client_hangups(asyncio.get_running_loop())
        if run_migrations:
            migrate()
        yield

    return lifespan


def create_app(run_migrations: bool = True) -> FastAPI:
    """Build the app. Tests pass run_migrations=False: they bring their own database."""
    app = FastAPI(title="Content Machine", docs_url=None, redoc_url=None,
                  lifespan=_lifespan(run_migrations))
    app.middleware("http")(remember_token)
    app.mount("/static", AppFiles(directory=STATIC_DIR), name="static")
    app.include_router(router)
    app.exception_handler(ChoiceError)(_refuse)
    return app


async def _refuse(request: Request, exc: ChoiceError) -> JSONResponse:
    """A rule about the managed lists was broken. The message says which, and the page's
    error banner shows it, so every route does not have to catch it."""
    return JSONResponse({"detail": str(exc)}, status_code=400)


app = create_app()
