"""
Nexura Phase 7 â€” DTO utility: compact_dict
Recursively purges None, "", and [] from dicts/lists.
Phase 7 Â§22: Shrinks network transfer by 30-50%.
"""
from __future__ import annotations
from typing import Any


def compact_dict(data: Any) -> Any:
    """Recursively remove None, empty string, and empty list values from a dict."""
    if isinstance(data, dict):
        return {
            k: compact_dict(v)
            for k, v in data.items()
            if v is not None and v != "" and v != []
        }
    if isinstance(data, list):
        return [compact_dict(item) for item in data if item is not None]
    return data
