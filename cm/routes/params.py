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
