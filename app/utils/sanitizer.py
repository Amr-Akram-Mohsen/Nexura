"""Text and HTML sanitization and URL canonicalization utilities."""

from __future__ import annotations
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import bleach

ALLOWED_TAGS = ["p", "h2", "h3", "blockquote", "ul", "ol", "li", "a", "code", "pre", "img", "strong", "em", "br"]
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"], "img": ["src", "alt", "width", "height"]}
DANGEROUS_TAGS = ["script", "style", "iframe", "object", "embed", "form"]

_TRACKING_PARAMS = frozenset({"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "session", "gclid", "msclkid"})
_MULTI_SPACE_RE = re.compile(r" {2,}")
_NBSP_RE = re.compile(r"\u00a0")
_NON_BREAKING_HYPHENS_RE = re.compile(r"[\u2011\u2013]")

_DANGEROUS_BLOCKS_RE = re.compile(r"<(script|style|iframe|object|embed|form)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_DANGEROUS_SELF_CLOSING_RE = re.compile(r"<(script|style|iframe|object|embed|form)\b[^>]*?/?>", re.IGNORECASE)


def sanitize_html(raw_html: str | None) -> str:
    """Sanitize HTML by stripping dangerous tags, normalizing Unicode, and collapsing whitespace."""
    if not raw_html:
        return ""

    text = html.unescape(raw_html)
    text = _DANGEROUS_BLOCKS_RE.sub("", text)
    text = _DANGEROUS_SELF_CLOSING_RE.sub("", text)

    text = bleach.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True, strip_comments=True)

    text = _NBSP_RE.sub(" ", text)
    text = _NON_BREAKING_HYPHENS_RE.sub("-", text)
    text = unicodedata.normalize("NFKC", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def sanitize_text(raw_text: str | None) -> str:
    """Plain-text sanitization with all HTML tags stripped."""
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
    """Strip tracking parameters (utm_*, ref, fbclid, etc.) and fragments from a URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        clean_params = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
        ]
        clean_query = urlencode(clean_params)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, ""))
    except Exception:
        return url.strip()
