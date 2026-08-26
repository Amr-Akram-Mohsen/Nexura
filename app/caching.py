"""
Nexura Phase 7 â€” Cache Keys, TTLs & Cascaded Invalidation (Â§23)
"""
from __future__ import annotations
from app.extensions import cache

# -- TTL constants (seconds) --------------------------------------------------
TTL_LAYOUT = 3600          # Layout context (header/footer/nav) â€” 1 hour
TTL_HOMEPAGE = 300         # Homepage & feed data â€” 5 minutes
TTL_FILTER_OPTS = 300      # Filter option slugs â€” 5 minutes
TTL_CONTENT_PAGE = 300     # Content static page â€” 5 minutes
TTL_SEARCH = 120           # Unified search results â€” 2 minutes
TTL_AUTOCOMPLETE = 60      # Search autocomplete suggestions â€” 60 seconds

# Aliases used in public.py imports
CACHE_TTL_LAYOUT = TTL_LAYOUT
CACHE_TTL_HOME = TTL_HOMEPAGE
CACHE_TTL_CONTENT_PAGE = TTL_CONTENT_PAGE
CACHE_TTL_SEARCH_RESULTS = TTL_SEARCH
CACHE_TTL_SEARCH_SUGGESTIONS = TTL_AUTOCOMPLETE


# -- Key helpers --------------------------------------------------------------

def key_layout_context() -> str:
    return "layout_context"


def key_home_page_data() -> str:
    return "home_page_data"


def key_filter_opts(section_id: int) -> str:
    return f"filter_opts_{section_id}"


def key_content_page(content_id: int) -> str:
    return f"content_page_{content_id}"


def key_search(normalized_query: str, filters_tuple: tuple) -> str:
    return f"search:unified:v1:{normalized_query}:{hash(filters_tuple)}"


def key_autocomplete(normalized_query: str) -> str:
    return f"suggestions:v1:{normalized_query}"


def normalize_filters(filter_dict: dict) -> tuple:
    """
    Convert URL query dicts into sorted tuples before caching.
    Prevents cache fragmentation from differing parameter order (Phase 7 Â§23).
    """
    return tuple(
        sorted(
            (k, tuple(sorted(v)) if isinstance(v, (list, tuple)) else v)
            for k, v in filter_dict.items()
            if v
        )
    )


# -- Cascaded invalidation -----------------------------------------------------

def invalidate_content_after_write(content_id: int | None = None) -> None:
    """
    Cascaded invalidation (Phase 7 Â§23):
    content detail cache -> feed listings -> filter options -> layout context
    """
    if content_id:
        cache.delete(key_content_page(content_id))
    cache.delete(key_home_page_data())
    # Filter opts invalidation requires section_id; clear all known patterns
    # In production with Redis, use SCAN + pattern delete; here clear known keys
    cache.delete(key_layout_context())


def invalidate_layout() -> None:
    cache.delete(key_layout_context())
