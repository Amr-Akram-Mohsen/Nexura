"""Cache keys, TTL configurations, and invalidation helpers."""

from __future__ import annotations
from app.extensions import cache

TTL_LAYOUT = 3600
TTL_HOMEPAGE = 300
TTL_FILTER_OPTS = 300
TTL_CONTENT_PAGE = 300
TTL_SEARCH = 120
TTL_AUTOCOMPLETE = 60

CACHE_TTL_LAYOUT = TTL_LAYOUT
CACHE_TTL_HOME = TTL_HOMEPAGE
CACHE_TTL_CONTENT_PAGE = TTL_CONTENT_PAGE
CACHE_TTL_SEARCH_RESULTS = TTL_SEARCH
CACHE_TTL_SEARCH_SUGGESTIONS = TTL_AUTOCOMPLETE


def key_layout_context() -> str:
    """Return cache key for layout navigation and footer context."""
    return "layout_context"


def key_home_page_data() -> str:
    """Return cache key for home feed and hero data."""
    return "home_page_data"


def key_filter_opts(section_id: int) -> str:
    """Return cache key for section filter options."""
    return f"filter_opts_{section_id}"


def key_content_page(content_id: int) -> str:
    """Return cache key for individual content item detail page."""
    return f"content_page_{content_id}"


def key_search(normalized_query: str, filters_tuple: tuple) -> str:
    """Return cache key for parameterized search results."""
    return f"search:unified:v1:{normalized_query}:{hash(filters_tuple)}"


def key_autocomplete(normalized_query: str) -> str:
    """Return cache key for query autocomplete suggestions."""
    return f"suggestions:v1:{normalized_query}"


def normalize_filters(filter_dict: dict) -> tuple:
    """Convert URL query dict into sorted immutable tuple to prevent key fragmentation."""
    return tuple(sorted((k, tuple(sorted(v)) if isinstance(v, (list, tuple)) else v) for k, v in filter_dict.items() if v))


def invalidate_content_after_write(content_id: int | None = None) -> None:
    """Invalidate content detail, home page data, and layout context caches."""
    if content_id:
        cache.delete(key_content_page(content_id))
    cache.delete(key_home_page_data())
    cache.delete(key_layout_context())


def invalidate_layout() -> None:
    """Invalidate layout navigation and footer cache."""
    cache.delete(key_layout_context())
