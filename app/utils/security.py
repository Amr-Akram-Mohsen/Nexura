"""Security and credential validation utilities."""

from __future__ import annotations
import re
from typing import Any

_LOWERCASE_RE = re.compile(r"[a-z]")
_UPPERCASE_RE = re.compile(r"[A-Z]")
_DIGIT_RE = re.compile(r"\d")
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


def score_password(password: str) -> dict[str, Any]:
    """Evaluate password strength (0-4) based on length and character class diversity."""
    if len(password) < 8:
        return {"score": 0, "valid": False, "message": "Must be at least 8 characters."}

    score = 0
    if _LOWERCASE_RE.search(password):
        score += 1
    if _UPPERCASE_RE.search(password):
        score += 1
    if _DIGIT_RE.search(password):
        score += 1
    if _SPECIAL_RE.search(password):
        score += 1

    if score < 2:
        return {"score": score, "valid": False, "message": "Too weak — add uppercase letters, numbers, or symbols."}

    return {"score": score, "valid": True, "message": ["", "Weak", "Fair", "Good", "Strong"][score]}


__all__ = ["score_password"]
