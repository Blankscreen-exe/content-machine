"""Small text helpers with no dependencies of their own."""
from __future__ import annotations

import re

SLUG_MAX = 50


def slugify(text: str) -> str:
    """A short, file-safe name: 'The cheapest decision?' -> 'the-cheapest-decision'."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not cleaned:
        return "untitled"
    if len(cleaned) <= SLUG_MAX:
        return cleaned
    # cut on a word boundary so the name stays readable
    return cleaned[:SLUG_MAX].rsplit("-", 1)[0] or cleaned[:SLUG_MAX]
