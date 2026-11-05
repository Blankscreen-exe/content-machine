"""Which themes exist, and which one a page wears.

A theme is one stylesheet in cm/static/themes/. The one chosen is stored as a setting, but
a theme can leave the folder after it was chosen, so the stored name is checked against
what is there rather than trusted: a page that linked a missing stylesheet would arrive
unstyled.
"""
from __future__ import annotations

from .crud import DEFAULT_SETTINGS
from .paths import THEMES_DIR


def available() -> list[str]:
    return sorted(path.stem for path in THEMES_DIR.glob("*.css"))


def resolve(name: str) -> str:
    """The theme to wear: the stored one while it exists, the default one if it is gone."""
    return name if name in available() else DEFAULT_SETTINGS["theme"]


def check(name: str) -> str:
    """For saving the setting: only a theme that is there can be chosen."""
    name = name.strip()
    if name not in available():
        raise ValueError(name)
    return name
