"""Text normalization and URL canonicalization facade re-exporting validation components."""

from __future__ import annotations
from app.ingestion.validation import normalize_title, jaccard_similarity, canonicalize_url

__all__ = ["normalize_title", "jaccard_similarity", "canonicalize_url"]
