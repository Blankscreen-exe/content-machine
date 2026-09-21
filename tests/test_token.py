"""The access token: it survives a restart, and can be replaced on purpose."""
from __future__ import annotations

import pytest

from cm import security
from cm.settings import get_settings


@pytest.fixture(autouse=True)
def stored_token(tmp_path, monkeypatch):
    """Use a temporary workspace and the real stored-token path, not the test override."""
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    monkeypatch.delenv("CM_TOKEN", raising=False)
    security.token.cache_clear()
    yield
    security.token.cache_clear()


def test_the_token_survives_a_restart():
    """A new token on every start would lock out every open tab, and lose unsaved text."""
    first = security.token()
    security.token.cache_clear()          # what a fresh process sees
    assert security.token() == first


def test_rotating_replaces_it():
    before = security.token()
    after = security.rotate_token()

    assert after != before
    assert security.token() == after


def test_the_override_wins(monkeypatch):
    monkeypatch.setenv("CM_TOKEN", "from-the-environment")
    security.token.cache_clear()
    assert security.token() == "from-the-environment"
