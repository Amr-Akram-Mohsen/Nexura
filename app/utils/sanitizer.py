"""
Nexura Phase 7 â€” Text & HTML Sanitization Pipeline (Â§8.2, Â§26)
4-stage mandatory pipeline for all scraped content and user inputs.
"""
from __future__ import annotations
import html
import re
import unicodedata

import bleach

# Phase 7 Â§8.2 allowed HTML tags (semantic markup only)
ALLOWED_TAGS = [
    "p", "h2", "h3", "blockquote", "ul", "ol", "li",
    "a", "code", "pre", "img", "strong", "em", "br",
]
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "width", "height"],
}

# Dangerous tags stripped completely (with content)
DANGEROUS_TAGS = ["script", "style", "iframe", "object", "embed", "form"]

# Regex for tracking parameters
_TRACKING_PARAMS_RE = re.compile(
    r"[?&](utm_[^&=]*|ref|fbclid|session)=[^&]*", re.IGNORECASE
)
_MULTI_SPACE_RE = re.compile(r" {2,}")
_NBSP_RE = re.compile(r"\u00a0")
_NON_BREAKING_HYPHENS_RE = re.compile(r"[\u2011\u2013]")


_DANGEROUS_BLOCKS_RE = re.compile(
    r"<(script|style|iframe|object|embed|form)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_DANGEROUS_SELF_CLOSING_RE = re.compile(
    r"<(script|style|iframe|object|embed|form)\b[^>]*?/?>",
    re.IGNORECASE,
)


def sanitize_html(raw_html: str | None) -> str:
    """
    Full 4-stage HTML sanitization pipeline (Phase 7 §8.2):
    1. Unescape HTML entities & strip dangerous blocks completely
    2. Tag filtering via bleach (allowed semantic tags only)
    3. Unicode normalization
    4. Whitespace collapsing
    """
    if not raw_html:
        return ""

    # Stage 1 — Unescape and completely purge dangerous elements + content
    text = html.unescape(raw_html)
    text = _DANGEROUS_BLOCKS_RE.sub("", text)
    text = _DANGEROUS_SELF_CLOSING_RE.sub("", text)

    # Stage 2 — Tag filtering via bleach
    text = bleach.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,           # strip disallowed tags (don't escape them)
        strip_comments=True,
    )

    # Stage 3 — Unicode normalization
    text = _NBSP_RE.sub(" ", text)
    text = _NON_BREAKING_HYPHENS_RE.sub("-", text)
    text = unicodedata.normalize("NFKC", text)

    # Stage 4 — Whitespace collapsing
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def sanitize_text(raw_text: str | None) -> str:
    """Plain-text sanitization (no HTML retained)."""
    if not raw_text:
        return ""
    text = html.unescape(raw_text)
    text = _DANGEROUS_BLOCKS_RE.sub("", text)
    text = _DANGEROUS_SELF_CLOSING_RE.sub("", text)
    text = bleach.clean(text, tags=[], strip=True)
    text = _NBSP_RE.sub(" ", text)
    text = _NON_BREAKING_HYPHENS_RE.sub("-", text)
    text = unicodedata.normalize("NFKC", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def canonicalize_url(url: str | None) -> str:
    """
    Strip tracking parameters from a URL (Phase 7 Â§10).
    Removes: utm_*, ref, fbclid, session
    """
    if not url:
        return ""
    url = _TRACKING_PARAMS_RE.sub("", url)
    # Clean up orphaned ? or & at end
    url = url.rstrip("?&")
    return url.strip()
