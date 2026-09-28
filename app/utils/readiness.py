"""Editorial readiness index facade re-exporting content_service components."""

from __future__ import annotations
from app.services.content_service import ReadinessResult, compute_readiness

__all__ = ["ReadinessResult", "compute_readiness"]
