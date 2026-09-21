"""Themes own appearance, including the appearance of anything we vendor."""
from __future__ import annotations

import pytest

from cm.paths import THEMES_DIR

THEMES = sorted(THEMES_DIR.glob("*.css"))


def test_there_is_at_least_one_theme():
    assert THEMES


@pytest.mark.parametrize("theme", THEMES, ids=lambda path: path.stem)
def test_a_theme_skins_the_editor(theme):
    """A theme that does not restyle the editor leaves a white widget in a themed page."""
    assert "toastui-editor" in theme.read_text(encoding="utf-8"), (
        f"{theme.name} does not skin the editor; see the other themes for the selectors"
    )


@pytest.mark.parametrize("theme", THEMES, ids=lambda path: path.stem)
def test_a_theme_keeps_the_toolbar_icons(theme):
    """`background:` on a toolbar button erases the icon, which is a background image."""
    for line in theme.read_text(encoding="utf-8").splitlines():
        if "toolbar-icons" in line and "background:" in line:
            pytest.fail(f"{theme.name}: use background-color here, or the icons disappear\n{line}")


@pytest.mark.parametrize("theme", THEMES, ids=lambda path: path.stem)
def test_a_theme_loads_nothing_from_the_internet(theme):
    assert "http://" not in theme.read_text(encoding="utf-8")
    assert "https://" not in theme.read_text(encoding="utf-8")
