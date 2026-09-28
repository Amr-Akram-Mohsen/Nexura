"""Validation, title deduplication, and quality gates for ingested content."""

from __future__ import annotations
from dataclasses import dataclass
import logging
import re
from typing import Sequence

from app.utils.sanitizer import canonicalize_url

log = logging.getLogger(__name__)

WORD_COUNT_THRESHOLD: int = 250
JACCARD_THRESHOLD: float = 0.85

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_MULTI_SPACE_RE = re.compile(r"\s+")


@dataclass
class GateResult:
    """Binary quality gate result for scraped articles."""

    passed: bool
    word_count: int | None
    has_image: bool
    reason: str


def check_article_quality(word_count: int | None, image_url: str | None) -> GateResult:
    """Verify article passes minimum word count and image presence criteria."""
    has_image = bool(image_url and image_url.strip())
    wc = word_count or 0

    if wc > WORD_COUNT_THRESHOLD and has_image:
        return GateResult(passed=True, word_count=wc, has_image=has_image, reason="")

    reasons = []
    if wc <= WORD_COUNT_THRESHOLD:
        reasons.append(f"word_count={wc} <= {WORD_COUNT_THRESHOLD}")
    if not has_image:
        reasons.append("image_url missing")

    return GateResult(passed=False, word_count=wc, has_image=has_image, reason="; ".join(reasons))


def normalize_title(title: str) -> list[str]:
    """Lowercase and strip punctuation to extract alphanumeric tokens."""
    lower = title.lower()
    no_punct = _PUNCT_RE.sub(" ", lower)
    tokens = _MULTI_SPACE_RE.sub(" ", no_punct).split()
    return [t for t in tokens if t]


def jaccard_similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
    """Calculate token Jaccard similarity: |A n B| / |A u B|."""
    set_a, set_b = set(tokens_a), set(tokens_b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


class DuplicateDetector:
    """Title deduplication checker using Jaccard token similarity."""

    def is_duplicate(self, candidate_title: str, existing_titles: Sequence[str]) -> bool:
        """Return True if candidate_title matches any existing title >= JACCARD_THRESHOLD."""
        candidate_tokens = normalize_title(candidate_title)
        for existing in existing_titles:
            existing_tokens = normalize_title(existing)
            score = jaccard_similarity(candidate_tokens, existing_tokens)
            if score >= JACCARD_THRESHOLD:
                log.debug("Duplicate detected (J=%.2f): %r vs %r", score, candidate_title[:60], existing[:60])
                return True
        return False

    def find_best_match(self, candidate_title: str, existing_titles: Sequence[str]) -> tuple[str | None, float]:
        """Return (best_matching_title, score) or (None, 0.0) if below threshold."""
        candidate_tokens = normalize_title(candidate_title)
        best_title, best_score = None, 0.0
        for existing in existing_titles:
            score = jaccard_similarity(candidate_tokens, normalize_title(existing))
            if score > best_score:
                best_score = score
                best_title = existing
        return (best_title, best_score) if best_score >= JACCARD_THRESHOLD else (None, 0.0)


__all__ = [
    "GateResult",
    "check_article_quality",
    "normalize_title",
    "jaccard_similarity",
    "canonicalize_url",
    "DuplicateDetector",
    "WORD_COUNT_THRESHOLD",
    "JACCARD_THRESHOLD",
]
