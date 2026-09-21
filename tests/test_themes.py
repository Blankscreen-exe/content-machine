"""Themes own appearance, including the appearance of anything we vendor."""
from __future__ import annotations

import pytest

from cm.models import IdeaStatus, Stage
from cm.paths import THEMES_DIR
from cm.templating import status_class

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


@pytest.mark.parametrize("theme", THEMES, ids=lambda path: path.stem)
def test_a_theme_colours_every_status_and_stage(theme):
    """A status with no colour would look like the others and lose its meaning."""
    css = theme.read_text(encoding="utf-8")
    missing = [value.value for value in (*IdeaStatus, *Stage) if f".{status_class(value.value)}" not in css]
    assert not missing, f"{theme.name} has no colour for: {', '.join(missing)}"


@pytest.mark.parametrize("theme", THEMES, ids=lambda path: path.stem)
def test_a_theme_skins_the_paging_controls(theme):
    """DataTables' defaults are plain grey; each theme sets its variables to match itself."""
    css = theme.read_text(encoding="utf-8")
    for variable in ("--dt-body_padding", "--dt-paging-button_background-current"):
        assert variable in css, f"{theme.name} does not set {variable}; see the other themes"


@pytest.mark.parametrize("theme", THEMES, ids=lambda path: path.stem)
def test_a_theme_draws_the_calendar(theme):
    """Without its own rules the month is an unlined grid; today and overdue would not show."""
    css = theme.read_text(encoding="utf-8")
    for selector in (".month td.day", ".month td.today", ".cal-piece.overdue"):
        assert selector in css, f"{theme.name} has no rule for {selector}"


@pytest.mark.parametrize("theme", THEMES, ids=lambda path: path.stem)
def test_a_theme_shows_unsaved_work_and_an_overlong_draft(theme):
    """Both are warnings; unstyled, they read as ordinary text and get missed."""
    css = theme.read_text(encoding="utf-8")
    for selector in (".unsaved-marker", ".char-count.over-limit"):
        assert selector in css, f"{theme.name} has no rule for {selector}"


@pytest.mark.parametrize("theme", THEMES, ids=lambda path: path.stem)
def test_a_theme_draws_the_drop_zone(theme):
    """An unmarked drop zone is invisible, and a drag over it would give no sign it will land."""
    css = theme.read_text(encoding="utf-8")
    for selector in (".drop-zone", ".drop-zone.dragging", ".asset-preview"):
        assert selector in css, f"{theme.name} has no rule for {selector}"
