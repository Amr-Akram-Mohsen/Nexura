"""
Nexura Phase 7 â€” Binary Quality Gate (Â§8.2)
Gate: word_count > 250 AND image_url present.
Failing articles are marked status='failed'; NOT deleted.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

WORD_COUNT_THRESHOLD = 250


@dataclass
class GateResult:
    passed: bool
    word_count: int | None
    has_image: bool
    reason: str


def check_article_quality(
    word_count: int | None,
    image_url: str | None,
) -> GateResult:
    """
    Phase 7 Â§8.2 binary quality gate:
      PASS: word_count > 250 AND image_url is not empty
      FAIL: either condition not met
    Failing articles are marked status='failed', not deleted.
    """
    has_image = bool(image_url and image_url.strip())
    wc = word_count or 0

    if wc > WORD_COUNT_THRESHOLD and has_image:
        return GateResult(passed=True, word_count=wc, has_image=has_image, reason="")

    reasons = []
    if wc <= WORD_COUNT_THRESHOLD:
        reasons.append(f"word_count={wc} <= {WORD_COUNT_THRESHOLD}")
    if not has_image:
        reasons.append("image_url missing")

    return GateResult(
        passed=False,
        word_count=wc,
        has_image=has_image,
        reason="; ".join(reasons),
    )
