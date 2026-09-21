"""Opening a folder in this computer's own file manager: Explorer, Finder, or whatever
the Linux desktop has set for folders."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class DesktopError(RuntimeError):
    """Raised with a message meant to be shown to the person."""


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(path)                               # Windows' own "open this"
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        raise DesktopError(f"Could not open {path}: {exc}. Open it yourself from the path shown.") from exc
