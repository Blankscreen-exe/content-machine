"""Access token.

The app can be served on the local network so you can use it from a phone, so it is not
open to anything that can reach the port. Every request carries a token, from the link
`cm serve` prints or from a cookie set on the first visit.

The token is kept in the workspace rather than made fresh on every start. A fresh one would
lock out every open tab each time the server restarts, and the natural fix — reloading the
page — throws away whatever you had typed. `cm token --rotate` replaces it deliberately.
"""
from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from fastapi import Cookie, HTTPException, Query, Request, status

from .settings import get_settings

COOKIE_NAME = "cm_token"


def _token_file() -> Path:
    return get_settings().workspace / ".cm" / "token"


@lru_cache
def token() -> str:
    """The current token. `CM_TOKEN` overrides the stored one (the tests use that)."""
    if override := os.environ.get("CM_TOKEN"):
        return override
    path = _token_file()
    if path.is_file() and (stored := path.read_text(encoding="utf-8").strip()):
        return stored
    return _write_new_token(path)


def rotate_token() -> str:
    """Replace the stored token. Every open tab and phone has to use the new link."""
    new = _write_new_token(_token_file())
    token.cache_clear()
    return new


def _write_new_token(path: Path) -> str:
    value = secrets.token_urlsafe(16)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return value


def require_token(t: str | None = Query(default=None),
                  cm_token: str | None = Cookie(default=None)) -> str:
    """Accept the token from ?t= or from the cookie."""
    for candidate in (t, cm_token):
        if candidate and secrets.compare_digest(candidate, token()):
            return candidate
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="bad or missing token")


async def remember_token(request: Request, call_next):
    """Middleware: arriving with ?t= stores the token in a cookie.

    This is middleware rather than part of the dependency because routes here return
    responses directly, and FastAPI only merges a dependency's response when it builds
    the response itself.
    """
    response = await call_next(request)
    supplied = request.query_params.get("t")
    if supplied and secrets.compare_digest(supplied, token()):
        response.set_cookie(COOKIE_NAME, supplied, httponly=True, samesite="lax")
    return response
