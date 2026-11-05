"""Request parameters shared by the page routes."""
from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator


def _blank_is_none(value: object) -> object:
    return None if value == "" else value


# A filter left on "all" arrives as `brand_id=` — an empty string, which is not an int.
# Browsers send it that way for an empty <select>, hidden input or number field, so accept
# it as "none".
OptionalInt = Annotated[int | None, BeforeValidator(_blank_is_none)]
OptionalId = OptionalInt           # the same rule, named for what most of them are


def back_to(next_url: str | None, fallback: str) -> str:
    """Where a form on a page of its own returns to: the page it was opened from.

    Only a path within this app is followed, so a link cannot send someone to another site
    once they save. Browsers read a path starting "//", or with a backslash, a tab or a
    newline in it, as possibly another site, so those fall back too.
    """
    if (next_url and next_url.startswith("/") and not next_url.startswith("//")
            and "\\" not in next_url and all(" " < char for char in next_url)):
        return next_url
    return fallback
