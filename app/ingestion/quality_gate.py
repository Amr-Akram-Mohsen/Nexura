"""Binary quality gate facade re-exporting validation components."""

from __future__ import annotations
from app.ingestion.validation import GateResult, check_article_quality, WORD_COUNT_THRESHOLD

__all__ = ["GateResult", "check_article_quality", "WORD_COUNT_THRESHOLD"]
