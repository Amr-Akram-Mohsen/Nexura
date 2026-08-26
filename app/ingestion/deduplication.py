"""
Nexura Phase 7 â€” Jaccard Deduplication (Â§10)
Threshold: >= 0.85 -> duplicate -> skip ingestion.
"""
from __future__ import annotations
import logging
from app.ingestion.normalizer import normalize_title, jaccard_similarity

log = logging.getLogger(__name__)

JACCARD_THRESHOLD: float = 0.85


class DuplicateDetector:
    """
    Checks whether an incoming article/video title is a duplicate of
    existing content already in the database.
    Phase 7 Â§10: Jaccard similarity >= 0.85 on lowercased, punctuation-stripped tokens.
    """

    def is_duplicate(self, candidate_title: str, existing_titles: list[str]) -> bool:
        """
        Return True if candidate_title is >= JACCARD_THRESHOLD similar
        to any title in existing_titles.
        """
        candidate_tokens = normalize_title(candidate_title)
        for existing in existing_titles:
            existing_tokens = normalize_title(existing)
            score = jaccard_similarity(candidate_tokens, existing_tokens)
            if score >= JACCARD_THRESHOLD:
                log.debug(
                    "Duplicate detected (J=%.2f): %r vs %r",
                    score, candidate_title[:60], existing[:60],
                )
                return True
        return False

    def find_best_match(
        self, candidate_title: str, existing_titles: list[str]
    ) -> tuple[str | None, float]:
        """Return (best_matching_title, score) or (None, 0.0) if no match."""
        candidate_tokens = normalize_title(candidate_title)
        best_title, best_score = None, 0.0
        for existing in existing_titles:
            score = jaccard_similarity(candidate_tokens, normalize_title(existing))
            if score > best_score:
                best_score = score
                best_title = existing
        return (best_title, best_score) if best_score >= JACCARD_THRESHOLD else (None, 0.0)
