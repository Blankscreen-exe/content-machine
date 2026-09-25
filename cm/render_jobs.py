"""Renders started from the web app, run in the background and followed from the page.

A render takes a minute or more, far longer than a request should wait, so it runs on a
thread of its own and the page asks how far it has got. What is known about each piece's
latest render is held here, in memory: it only matters while the app is running, and a
finished video is in the piece's assets whatever happens to this.

One render per piece at a time from the app. The command line keeps no such record, but
every render has a job folder of its own (renders.py), so the two never collide.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import renders, video


class AlreadyRendering(RuntimeError):
    """This piece has a render running already."""


@dataclass
class Job:
    piece_id: int
    draft: bool
    state: str = "running"          # running, done or failed
    progress: str = "Starting"
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None
    result: Path | None = None
    error: str = ""

    @property
    def running(self) -> bool:
        return self.state == "running"

    @property
    def elapsed(self) -> str:
        seconds = int((self.finished or time.monotonic()) - self.started)
        return f"{seconds // 60}:{seconds % 60:02d}"


_jobs: dict[int, Job] = {}
_lock = threading.Lock()


def latest(piece_id: int) -> Job | None:
    return _jobs.get(piece_id)


def start(plan: renders.Plan, draft: bool) -> Job:
    """Start rendering `plan` in the background, unless the piece is already rendering."""
    with _lock:
        current = _jobs.get(plan.piece_id)
        if current and current.running:
            raise AlreadyRendering(f"A {'draft' if current.draft else 'final'} render of this piece "
                                   f"is running ({current.progress}). Wait for it to finish.")
        job = _jobs[plan.piece_id] = Job(piece_id=plan.piece_id, draft=draft)
    _spawn(lambda: _run(job, plan))
    return job


def _run(job: Job, plan: renders.Plan) -> None:
    try:
        job.result = renders.run(plan, draft=job.draft, on_progress=lambda p: setattr(job, "progress", str(p)))
        job.state = "done"
    except video.RenderError as exc:
        job.error, job.state = str(exc), "failed"
    except Exception as exc:                     # on a thread, an error nobody reads is lost
        job.error, job.state = f"The render stopped unexpectedly: {exc!r}", "failed"
    finally:
        job.finished = time.monotonic()


def _spawn(target) -> None:
    """Run `target` in the background. The app may stop while a render runs; the render
    process it started then finishes or fails on its own."""
    threading.Thread(target=target, daemon=True, name="render").start()
