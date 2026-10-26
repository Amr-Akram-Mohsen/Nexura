"""Public routes blueprint for feeds, taxonomies, details, and search."""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import cache, db
from app.caching import (
    CACHE_TTL_HOME,
    CACHE_TTL_HOME_FOR_YOU,
    CACHE_TTL_SEARCH_RESULTS,
    CACHE_TTL_SEARCH_SUGGESTIONS,
    CACHE_TTL_LAYOUT,
    key_home_for_you,
    invalidate_home_for_you,
)
from app.repositories.content_repo import ContentRepository
from app.repositories.taxonomy_repo import TaxonomyRepository
from app.repositories.search_repo import SearchRepository
from app.repositories.analytics_repo import AnalyticsRepository
from app.serializers.content_serializers import serialize_content_card
from app.services.content_service import ContentService
from app.services.recommendation_service import RecommendationService, trending_reason
from config import SOCIAL_LINKS

log = logging.getLogger(__name__)

public_bp = Blueprint("public", __name__)


@public_bp.route("/health")
def health_check():
    """Liveness and infrastructure readiness probe."""
    try:
        db.session.execute(db.text("SELECT 1"))
        db_status = "healthy"
    except Exception as exc:
        db_status = f"unhealthy: {exc}"

    cache_status = "operational" if cache else "unconfigured"
    status_code = 200 if db_status == "healthy" else 503

    return jsonify({
        "status": "ok" if status_code == 200 else "degraded",
        "database": db_status,
        "cache": cache_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), status_code


@public_bp.app_context_processor
def inject_nav_context() -> dict[str, Any]:
    """Inject active navigation sections and global links into templates."""
    cached = cache.get("layout_context")
    if cached is None:
        sections = TaxonomyRepository.get_active_sections()
        cached = {"sections": [{"name": s.name, "slug": s.slug} for s in sections]}
        cache.set("layout_context", cached, timeout=CACHE_TTL_LAYOUT)

    return {"nav_sections": cached["sections"], "active_section": None, "current_year": datetime.now(timezone.utc).year, "social_links": SOCIAL_LINKS}


def _record_view(content_id: int) -> None:
    """Record a page view for authenticated or anonymous visitors."""
    try:
        if current_user.is_authenticated:
            AnalyticsRepository.record_view(content_id=content_id, user_id=current_user.id)
            invalidate_home_for_you(current_user.id)
        else:
            AnalyticsRepository.record_view(content_id=content_id, ip_address=request.remote_addr)
    except Exception as exc:
        log.debug("View tracking error: %s", exc)


def _user_state(content_id: int) -> dict[str, bool]:
    """Fetch like, dislike, and save state for the active user."""
    if not current_user.is_authenticated:
        return {"liked": False, "disliked": False, "saved": False}
    return AnalyticsRepository.get_user_state(current_user.id, content_id)


def _extract_content_id(slug_or_id: str | int | None) -> int | None:
    """Extract integer content ID from slug or numeric identifier."""
    if slug_or_id is None:
        return None
    if isinstance(slug_or_id, int):
        return slug_or_id
    s = str(slug_or_id).strip()
    if s.isdigit():
        return int(s)
    prefix = s.split("-", 1)[0]
    return int(prefix) if prefix.isdigit() else None


def _prepare_detail_view(content_id: int, slug_or_id: str | int | None, endpoint: str):
    """Validate content, enforce canonical slug redirect, and record view."""
    content_live = ContentRepository.get_published_content(content_id)
    if not content_live:
        abort(404)

    if content_live.slug:
        expected_slug = content_live.slug_id
        if slug_or_id != expected_slug:
            return None, redirect(url_for(endpoint, slug_or_id=expected_slug), code=301)

    _record_view(content_id)
    return content_live, None


def _parse_pagination_params() -> tuple[int, str | None]:
    """Extract standard page number and optional content type filter from query params."""
    return request.args.get("page", 1, type=int), request.args.get("type")


def _resolve_detail_page(
    slug_or_id: str | int | None,
    content_id: int | None,
    expected_type: str,
    endpoint: str,
) -> tuple[dict[str, Any] | None, Any]:
    """Validate content, enforce canonical slug redirect, and assemble shared detail context."""
    cid = _extract_content_id(slug_or_id if slug_or_id is not None else content_id)
    if not cid:
        abort(404)

    page_data = ContentService.get_detail_page_data(cid, expected_type)
    if not page_data:
        abort(404)

    content_live, redirect_resp = _prepare_detail_view(cid, slug_or_id, endpoint)
    if redirect_resp:
        return None, redirect_resp

    for attr in (
        "section_slug",
        "section_name",
        "category_slug",
        "category_name",
        "formatted_date",
        "formatted_date_long",
        "reading_time_text",
    ):
        if attr in page_data:
            setattr(content_live, attr, page_data[attr])

    uid = current_user.id if current_user.is_authenticated else None
    shared_context = {
        "content": content_live,
        "related_items": page_data.get("related"),
        "user_state": _user_state(cid),
        "comments_tree": AnalyticsRepository.get_comments_tree(cid, current_user_id=uid),
        "breadcrumbs": page_data.get("breadcrumbs"),
        "formatted_date_long": page_data.get("formatted_date_long"),
        "reading_time_text": page_data.get("reading_time_text"),
    }
    return page_data, shared_context


def _render_newsletter_feedback(result: dict[str, Any], success_title: str, fail_title: str):
    """Render newsletter confirmation/unsubscription feedback with consistent status code."""
    success = result.get("success", False)
    return render_template(
        "public/newsletter_feedback.html",
        title=success_title if success else fail_title,
        message=result.get("message"),
        success=success,
    ), (200 if success else 400)


HOME_SHELF_SIZE = 6
HOME_SHELF_FETCH = HOME_SHELF_SIZE + 2  # headroom for hero overlap when a cached shelf outlives the hero data


def _serialize_shelf_items(entries) -> list[dict[str, Any]]:
    """Serialize (content, reason) pairs into card payloads carrying the recommendation reason."""
    cards = []
    for content, reason in entries:
        card = serialize_content_card(content)
        if reason:
            card["recommendation_reason"] = reason
        cards.append(card)
    return cards


def _build_for_you_shelf(hero_items: list[dict[str, Any]], trending_picks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve the homepage shelf: personalized for readers with history, trending for everyone else."""
    items = trending_picks
    personalized = False

    if current_user.is_authenticated:
        cache_key = key_home_for_you(current_user.id)
        payload = cache.get(cache_key)
        if payload is None:
            feed = RecommendationService.get_personalized_feed_with_reasons(
                current_user.id, limit=HOME_SHELF_FETCH, exclude_ids=[h.get("id") for h in hero_items]
            )
            payload = {"personalized": feed.personalized, "items": _serialize_shelf_items(feed.entries)}
            cache.set(cache_key, payload, timeout=CACHE_TTL_HOME_FOR_YOU)
        if payload["personalized"]:
            items, personalized = payload["items"], True

    hero_ids = {h.get("id") for h in hero_items}
    items = [item for item in items if item.get("id") not in hero_ids][:HOME_SHELF_SIZE]
    if not items:
        return None

    if personalized:
        title, subtitle = "Recommended For You", "Picked from your reading history and saved stories."
    elif current_user.is_authenticated:
        title, subtitle = "Trending Now", "Read and save a few stories and we'll tailor this shelf to you."
    else:
        title, subtitle = "Trending Now", "What readers are exploring on Nexura right now."

    return {"title": title, "subtitle": subtitle, "items": items, "personalized": personalized}


@public_bp.route("/")
def home():
    """Render home feed with hero banner, personalized shelf, section rows, and trending entities."""
    page_data = cache.get("home_page_data")

    if page_data is None or "trending_picks" not in page_data:
        sections = TaxonomyRepository.get_active_sections()
        hero_items = [serialize_content_card(c) for c in ContentRepository.get_hero_items(limit=5)]

        section_rows = []
        for section_obj in sections[:3]:
            items = ContentRepository.list_published(section_id=section_obj.id, page=1, per_page=18).items
            serialized = [serialize_content_card(c) for c in items]
            section_rows.append({"name": section_obj.name, "slug": section_obj.slug, "content_items": serialized, "items": serialized})

        trending_entities = TaxonomyRepository.get_trending_entities(limit=20)
        trending_items = RecommendationService.get_trending_items(limit=HOME_SHELF_FETCH, exclude_ids=[h["id"] for h in hero_items])
        trending_picks = _serialize_shelf_items([(c, trending_reason(c)) for c in trending_items])

        page_data = {
            "hero_items": hero_items,
            "section_rows": section_rows,
            "trending_entities": [{"name": e.name, "slug": e.slug} for e in trending_entities],
            "trending_picks": trending_picks,
        }
        cache.set("home_page_data", page_data, timeout=CACHE_TTL_HOME)

    for_you = _build_for_you_shelf(page_data["hero_items"], page_data["trending_picks"])

    return render_template(
        "public/home.html",
        hero_items=page_data["hero_items"],
        section_rows=page_data["section_rows"],
        trending_entities=page_data["trending_entities"],
        for_you=for_you,
    )


@public_bp.route("/<section_slug>")
def section(section_slug: str):
    """Render section landing page with categories and paginated items."""
    section_obj = TaxonomyRepository.get_section_by_slug(section_slug)
    if not section_obj:
        abort(404)

    page, content_type = _parse_pagination_params()
    category_slug = request.args.get("category")

    category_id = None
    if category_slug:
        cat = TaxonomyRepository.get_category_by_slug(category_slug)
        category_id = cat.id if cat else None

    pagination_obj = ContentRepository.list_published(
        section_id=section_obj.id, category_id=category_id, object_type=content_type or None, page=page, per_page=24
    )

    items = [serialize_content_card(c) for c in pagination_obj.items]
    filter_options = {"categories": TaxonomyRepository.get_categories_for_section(section_obj.id)}

    return render_template(
        "public/section.html",
        section=section_obj,
        active_section=section_slug,
        items=items,
        filter_options=filter_options,
        content_type=content_type,
        category_slug=category_slug,
        page=page,
        total=pagination_obj.total,
        total_pages=pagination_obj.pages,
    )


@public_bp.route("/<section_slug>/<category_slug>")
def category(section_slug: str, category_slug: str):
    """Render category landing page with subcategories and items."""
    section_obj = TaxonomyRepository.get_section_by_slug(section_slug)
    if not section_obj:
        abort(404)

    cat_obj = TaxonomyRepository.get_category_by_slug(category_slug)
    if not cat_obj:
        abort(404)

    page, content_type = _parse_pagination_params()

    pagination_obj = ContentRepository.list_published(
        section_id=section_obj.id, category_id=cat_obj.id, object_type=content_type or None, page=page, per_page=24
    )

    items = [serialize_content_card(c) for c in pagination_obj.items]
    subcategories = TaxonomyRepository.get_subcategories(cat_obj.id)

    return render_template(
        "public/category.html",
        section=section_obj,
        category=cat_obj,
        active_section=section_slug,
        items=items,
        subcategories=subcategories,
        content_type=content_type,
        page=page,
        total=pagination_obj.total,
        total_pages=pagination_obj.pages,
    )


@public_bp.route("/topic/<entity_slug>")
def topic(entity_slug: str):
    """Render topic landing page for a specific named entity."""
    entity = TaxonomyRepository.get_entity_by_slug(entity_slug)
    if not entity:
        abort(404)

    page, content_type = _parse_pagination_params()

    pagination_obj = ContentRepository.list_by_entity(entity_id=entity.id, object_type=content_type or None, page=page, per_page=24)

    items = [serialize_content_card(c) for c in pagination_obj.items]
    related_entities = TaxonomyRepository.get_related_entities(entity.id, limit=10)

    return render_template(
        "public/topic.html",
        entity=entity,
        items=items,
        related_entities=related_entities,
        content_type=content_type,
        page=page,
        total=pagination_obj.total,
        total_pages=pagination_obj.pages,
    )


@public_bp.route("/article/<slug_or_id>")
@public_bp.route("/article/<int:content_id>")
def article(slug_or_id: str | None = None, content_id: int | None = None):
    """Render article detail view with authors, sources, entities, and comments."""
    page_data, context_or_redirect = _resolve_detail_page(slug_or_id, content_id, "article", "public.article")
    if page_data is None:
        return context_or_redirect

    context_or_redirect.update({
        "article": page_data["article"],
        "authors": page_data.get("authors", []),
        "source": page_data.get("source"),
        "entities": page_data.get("entities", []),
    })
    return render_template("public/article.html", **context_or_redirect)


@public_bp.route("/video/<slug_or_id>")
@public_bp.route("/video/<int:content_id>")
def video(slug_or_id: str | None = None, content_id: int | None = None):
    """Render video detail view with player, comments, and related items."""
    page_data, context_or_redirect = _resolve_detail_page(slug_or_id, content_id, "video", "public.video")
    if page_data is None:
        return context_or_redirect

    context_or_redirect.update({
        "video": page_data["video"],
        "yt_comments": page_data.get("yt_comments", []),
        "duration_formatted": page_data.get("duration_formatted"),
    })
    return render_template("public/video.html", **context_or_redirect)


@public_bp.route("/search")
def search():
    """Render search results page with keyword, type, section, and sort filters.
    When no query is provided, renders a discovery state with trending content.
    """
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    object_type = request.args.get("type")
    section_slug = request.args.get("section")
    sort = request.args.get("sort", "relevance")

    if sort not in ("relevance", "recent", "popular"):
        sort = "relevance"

    section_id = None
    if section_slug:
        sec = TaxonomyRepository.get_section_by_slug(section_slug)
        if sec:
            section_id = sec.id

    # Always load trending entities for suggestion chips
    trending_entities_cache_key = "trending_entities:search_page"
    trending_entities = cache.get(trending_entities_cache_key)
    if trending_entities is None:
        trending_entities = TaxonomyRepository.get_trending_entities(limit=14)
        cache.set(trending_entities_cache_key, trending_entities, timeout=CACHE_TTL_HOME)

    items = []
    total = 0
    total_pages = 1
    trending = []

    if not q:
        # Zero-query: discovery state — show trending content
        trending_cache_key = "trending_content:search_page"
        trending = cache.get(trending_cache_key)
        if trending is None:
            trending_raw = ContentRepository.get_trending(limit=6)
            trending = [serialize_content_card(c) for c in trending_raw]
            cache.set(trending_cache_key, trending, timeout=CACHE_TTL_HOME)
    else:
        cache_key = f"search:v2:{q.lower()}:{page}:{object_type}:{section_slug}:{sort}"
        cached = cache.get(cache_key)

        if cached is None:
            pagination_obj = ContentRepository.search_published(
                query=q, object_type=object_type or None,
                section_id=section_id, sort=sort, page=page, per_page=24,
            )
            items = [serialize_content_card(c) for c in pagination_obj.items]
            cache.set(cache_key, {"items": items, "total": pagination_obj.total, "pages": pagination_obj.pages}, timeout=CACHE_TTL_SEARCH_RESULTS)
            total = pagination_obj.total
            total_pages = pagination_obj.pages
        else:
            items = cached["items"]
            total = cached["total"]
            total_pages = cached["pages"]

    return render_template(
        "public/search.html",
        items=items,
        query=q,
        total=total,
        page=page,
        total_pages=total_pages,
        sort=sort,
        object_type=object_type,
        section_slug=section_slug,
        trending=trending,
        trending_entities=trending_entities,
    )


@public_bp.route("/api/search/suggestions")
def search_suggestions():
    """Return autocomplete search suggestions for articles and videos."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"error": "Query too short"}), 400

    cache_key = f"suggestions:v1:{q.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)

    results = SearchRepository.autocomplete(q, limit=5)
    payload = {
        "articles": [
            {
                "title": r.title,
                "url": url_for("public.article", slug_or_id=getattr(r, "slug_id", r.id)),
                "thumb": getattr(r, "_article_obj", None).image_url if getattr(r, "_article_obj", None) else None,
                "category": r.category.name if r.category else None,
            }
            for r in results.get("articles", [])
        ],
        "videos": [
            {
                "title": r.title,
                "url": url_for("public.video", slug_or_id=getattr(r, "slug_id", r.id)),
                "thumb": getattr(r, "_video_obj", None).thumbnail_url if getattr(r, "_video_obj", None) else None,
                "channel": getattr(r, "_video_obj", None).channel_name if getattr(r, "_video_obj", None) else None,
            }
            for r in results.get("videos", [])
        ],
    }

    cache.set(cache_key, payload, timeout=CACHE_TTL_SEARCH_SUGGESTIONS)
    return jsonify(payload)


@public_bp.route("/about")
def about():
    """Render about page."""
    return render_template("public/about.html")


@public_bp.route("/contact", methods=["GET", "POST"])
def contact():
    """Render contact and editorial tip submission page."""
    return render_template("public/contact.html", submitted=(request.method == "POST"))


@public_bp.route("/terms")
def terms():
    """Render terms of service page."""
    return render_template("public/terms.html")


@public_bp.route("/privacy")
def privacy():
    """Render privacy policy page."""
    return render_template("public/privacy.html")


@public_bp.route("/newsletter/confirm/<token>")
def confirm_newsletter(token: str):
    """Confirm a newsletter subscription via double opt-in link."""
    from app.services.newsletter_service import confirm_subscription
    return _render_newsletter_feedback(confirm_subscription(token), "Subscription Confirmed", "Confirmation Failed")


@public_bp.route("/newsletter/unsubscribe/<token>")
def unsubscribe_newsletter(token: str):
    """Unsubscribe from Nexura newsletter."""
    from app.services.newsletter_service import unsubscribe_newsletter
    return _render_newsletter_feedback(unsubscribe_newsletter(token), "Unsubscribed", "Unsubscribe Failed")

