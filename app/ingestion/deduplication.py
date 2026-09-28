"""Deduplication facade re-exporting validation components."""

from __future__ import annotations
from app.ingestion.validation import DuplicateDetector, JACCARD_THRESHOLD

__all__ = ["DuplicateDetector", "JACCARD_THRESHOLD"]
