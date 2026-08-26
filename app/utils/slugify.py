"""Nexura Phase 7 â€” Slug utilities."""
from __future__ import annotations
from slugify import slugify as _slugify


def make_slug(text: str, max_length: int = 255) -> str:
    """Create a URL-safe slug from arbitrary text."""
    return _slugify(text, max_length=max_length, word_boundary=True)
