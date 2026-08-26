"""
Nexura Phase 7 â€” Text normalization & URL canonicalization (Â§10, Â§8.2)
"""
from __future__ import annotations
import re
import string
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

# Tracking parameters to strip (Phase 7 Â§10)
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "fbclid", "session", "gclid", "msclkid",
})

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_MULTI_SPACE_RE = re.compile(r"\s+")


def normalize_title(title: str) -> list[str]:
    """
    Phase 7 Â§10: Lowercase, strip punctuation, extract alphanumeric tokens.
    Returns list of tokens for Jaccard similarity computation.
    """
    lower = title.lower()
    no_punct = _PUNCT_RE.sub(" ", lower)
    tokens = _MULTI_SPACE_RE.sub(" ", no_punct).split()
    return [t for t in tokens if t]


def jaccard_similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
    """
    Token Jaccard similarity J(A,B) = |A n B| / |A ? B| (Phase 7 Â§10).
    """
    set_a, set_b = set(tokens_a), set(tokens_b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union


def canonicalize_url(url: str) -> str:
    """
    Strip tracking parameters from URL (Phase 7 Â§10).
    Removes utm_*, ref, fbclid, session.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        clean_params = [
            (k, v) for k, v in parse_qsl(parsed.query)
            if k.lower() not in _TRACKING_PARAMS
        ]
        clean_query = urlencode(clean_params)
        return urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, clean_query, "",  # strip fragment
        ))
    except Exception:
        return url
