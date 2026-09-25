"""Handing files to the browser: a piece's assets and takes, a brand's resources, and the
app's own scripts and styles.

Files keep their name when their contents change: `draft.mp4` after every draft render,
`voice.js` after every update to the app. So the browser is told to check back each time
(`no-cache`); an unchanged file then costs a short "not modified" answer, and a changed
one is never used stale.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .. import assets

CHECK_BACK = {"Cache-Control": "no-cache"}


def stored_file(path: Path) -> FileResponse:
    """The file, with its own content type. Answers range requests, so video can be scrubbed."""
    return FileResponse(path, media_type=assets.media_type(path), headers=CHECK_BACK)


class AppFiles(StaticFiles):
    """The app's static files, which the browser checks back on, so an update reaches it."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers.update(CHECK_BACK)
        return response
