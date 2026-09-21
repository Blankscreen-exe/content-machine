"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import migrate
from .paths import STATIC_DIR
from .routes import router
from .security import remember_token


def _lifespan(run_migrations: bool):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if run_migrations:
            migrate()
        yield

    return lifespan


def create_app(run_migrations: bool = True) -> FastAPI:
    """Build the app. Tests pass run_migrations=False: they bring their own database."""
    app = FastAPI(title="Content Machine", docs_url=None, redoc_url=None,
                  lifespan=_lifespan(run_migrations))
    app.middleware("http")(remember_token)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(router)
    return app


app = create_app()
