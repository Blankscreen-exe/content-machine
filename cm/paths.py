"""Where the app's own files live (templates, stylesheets, vendored scripts)."""
from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"
THEMES_DIR = STATIC_DIR / "themes"
