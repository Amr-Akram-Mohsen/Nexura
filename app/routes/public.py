"""
Nexura Phase 7 — Public Routes Blueprint (§12)
Handles home, section, category, topic, article, video, search, autocomplete API.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

from flask import (
    Blueprint, abort, jsonify, redirect, render_template,
    request, url_for, current_app,
)
from flask_login import current_user

from app.extensions import cache, db
from app.caching import (
    CACHE_TTL_HOME, CACHE_TTL_CONTENT_PAGE,
    CACHE_TTL_SEARCH_RESULTS, CACHE_TTL_SEARCH_SUGGESTIONS,
    CACHE_TTL_LAYOUT,
)
from app.models.taxonomy import Section, Category, Entity
from app.models.content import Content, Article
from app.models.video import Video, VideoComment
from app.models.source import Source
from app.models.interaction import View
from app.repositories.content_repo import ContentRepository
from app.repositories.article_repo import ArticleRepository
from app.repositories.video_repo import VideoRepository
from app.repositories.taxonomy_repo import TaxonomyRepository
from app.repositories.search_repo import SearchRepository
from app.repositories.user_repo import UserRepository
from app.repositories.analytics_repo import AnalyticsRepository
from app.serializers.content_serializers import serialize_content_card, serialize_content_detail

log = logging.getLogger(__name__)

public_bp = Blueprint("public", __name__)


# ─── Context processor — inject nav_sections into all templates ───────────────
@public_bp.app_context_processor
def inject_nav_context() -> dict[str, Any]:
    """Provides nav_sections and active_section to every template."""
    cached = cache.get("layout_context")
    if cached is None:
        sections = TaxonomyRepository.get_active_sections()
        cached = {"sections": [{"name": s.name, "slug": s.slug} for s in sections]}
        cache.set("layout_context", cached, timeout=CACHE_TTL_LAYOUT)

    return {
        "nav_sections": cached["sections"],
        "active_section": None,
        "current_year": datetime.now(timezone.utc).year,
    }


# ─── Helper: record view ────────────────────────────────────────────────────
def _record_view(content_id: int) -> None:
    """Idempotently record a page view for authenticated or anonymous users."""
    try:
        ip = request.remote_addr
        if current_user.is_authenticated:
            AnalyticsRepository.record_view(
                content_id=content_id, user_id=current_user.id
            )
        else:
            AnalyticsRepository.record_view(
                content_id=content_id, ip_address=ip
            )
    except Exception as exc:
        log.debug("View tracking error: %s", exc)


# ─── Helper: build user state (liked / disliked / saved) ────────────────────
def _user_state(content_id: int) -> dict:
    if not current_user.is_authenticated:
        return {"liked": False, "disliked": False, "saved": False}
    return AnalyticsRepository.get_user_state(current_user.id, content_id)


# ─── Home ────────────────────────────────────────────────────────────────────
@public_bp.route("/")
def home():
    page_data = cache.get("home_page_data")

    if page_data is None:
        sections = TaxonomyRepository.get_active_sections()

        # Hero: top 5 most viewed recent published contents
        hero_items = [
            serialize_content_card(c)
            for c in ContentRepository.get_hero_items(limit=5)
        ]

        # Section rows: up to 3 active sections, each with 12 items
        section_rows = []
        for section in sections[:3]:
            items = ContentRepository.list_published(
                section_id=section.id, page=1, per_page=12
            ).items
            section_rows.append({
                "name": section.name,
                "slug": section.slug,
                "content_items": [serialize_content_card(c) for c in items],
                "items": [serialize_content_card(c) for c in items],
            })

        # Trending entities
        trending_entities = TaxonomyRepository.get_trending_entities(limit=20)

        page_data = {
            "hero_items": hero_items,
            "section_rows": section_rows,
            "trending_entities": [
                {"name": e.name, "slug": e.slug} for e in trending_entities
            ],
        }
        cache.set("home_page_data", page_data, timeout=CACHE_TTL_HOME)

    return render_template(
        "public/home.html",
        hero_items=page_data["hero_items"],
        section_rows=page_data["section_rows"],
        trending_entities=page_data["trending_entities"],
    )


# ─── Section ─────────────────────────────────────────────────────────────────
@public_bp.route("/<section_slug>")
def section(section_slug: str):
    section_obj = TaxonomyRepository.get_section_by_slug(section_slug)
    if not section_obj:
        abort(404)

    page = request.args.get("page", 1, type=int)
    content_type = request.args.get("type")
    category_slug = request.args.get("category")

    category_id = None
    if category_slug:
        cat = db.session.query(Category).filter(Category.slug == category_slug).first()
        category_id = cat.id if cat else None

    pagination_obj = ContentRepository.list_published(
        section_id=section_obj.id,
        category_id=category_id,
        object_type=content_type or None,
        page=page,
        per_page=24,
    )

    items = [serialize_content_card(c) for c in pagination_obj.items]
    filter_options = {
        "categories": TaxonomyRepository.get_categories_for_section(section_obj.id)
    }

    return render_template(
        "public/section.html",
        section=section_obj,
        active_section=section_slug,
        items=items,
        filter_options=filter_options,
        page=page,
        total=pagination_obj.total,
        total_pages=pagination_obj.pages,
    )


# ─── Category ─────────────────────────────────────────────────────────────────
@public_bp.route("/<section_slug>/<category_slug>")
def category(section_slug: str, category_slug: str):
    section_obj = TaxonomyRepository.get_section_by_slug(section_slug)
    if not section_obj:
        abort(404)

    cat_obj = db.session.query(Category).filter(Category.slug == category_slug).first()
    if not cat_obj:
        abort(404)

    page = request.args.get("page", 1, type=int)
    content_type = request.args.get("type")

    pagination_obj = ContentRepository.list_published(
        section_id=section_obj.id,
        category_id=cat_obj.id,
        object_type=content_type or None,
        page=page,
        per_page=24,
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
        page=page,
        total=pagination_obj.total,
        total_pages=pagination_obj.pages,
    )


# ─── Topic / Entity ───────────────────────────────────────────────────────────
@public_bp.route("/topic/<entity_slug>")
def topic(entity_slug: str):
    entity = db.session.query(Entity).filter(Entity.slug == entity_slug).first()
    if not entity:
        abort(404)

    page = request.args.get("page", 1, type=int)
    content_type = request.args.get("type")

    pagination_obj = ContentRepository.list_by_entity(
        entity_id=entity.id,
        object_type=content_type or None,
        page=page,
        per_page=24,
    )

    items = [serialize_content_card(c) for c in pagination_obj.items]
    related_entities = TaxonomyRepository.get_related_entities(entity.id, limit=10)

    return render_template(
        "public/topic.html",
        entity=entity,
        items=items,
        related_entities=related_entities,
        page=page,
        total=pagination_obj.total,
        total_pages=pagination_obj.pages,
    )


# ─── Article Detail ───────────────────────────────────────────────────────────
@public_bp.route("/article/<int:content_id>")
def article(content_id: int):
    cache_key = f"content_page_{content_id}"
    page_data = cache.get(cache_key)

    if page_data is None:
        content = ContentRepository.get_published_content(content_id)
        if not content or content.object_type != "article":
            abort(404)

        article_obj = db.session.get(Article, content.object_id)
        if not article_obj:
            abort(404)

        authors = ArticleRepository.get_authors(article_obj.id)
        source = db.session.get(Source, content.source_id) if content.source_id else None
        entities = ContentRepository.get_entities_for_content(content_id)
        related_items = ContentRepository.get_related_content(
            content_id, limit=6
        )

        page_data = {
            "content": content,
            "article": article_obj,
            "authors": authors,
            "source": source,
            "entities": entities,
            "related": [serialize_content_card(r) for r in related_items],
            "section_slug": content.section.slug if content.section else None,
            "section_name": content.section.name if content.section else None,
            "category_slug": content.category.slug if content.category else None,
            "category_name": content.category.name if content.category else None,
        }
        cache.set(cache_key, page_data, timeout=CACHE_TTL_CONTENT_PAGE)

    _record_view(content_id)
    user_state = _user_state(content_id)

    # Enrich content object with section/category for template
    content = page_data["content"]
    # Attach names from page_data to content for template access
    content.section_slug = page_data.get("section_slug")
    content.section_name = page_data.get("section_name")
    content.category_slug = page_data.get("category_slug")
    content.category_name = page_data.get("category_name")

    return render_template(
        "public/article.html",
        content=content,
        article=page_data["article"],
        authors=page_data["authors"],
        source=page_data["source"],
        entities=page_data["entities"],
        related_items=page_data["related"],
        user_state=user_state,
    )


# ─── Video Detail ─────────────────────────────────────────────────────────────
@public_bp.route("/video/<int:content_id>")
def video(content_id: int):
    cache_key = f"content_page_{content_id}"
    page_data = cache.get(cache_key)

    if page_data is None:
        content = ContentRepository.get_published_content(content_id)
        if not content or content.object_type != "video":
            abort(404)

        video_obj = db.session.get(Video, content.object_id)
        if not video_obj:
            abort(404)

        yt_comments = VideoRepository.get_top_comments(video_obj.id, limit=15)
        related_items = ContentRepository.get_related_content(content_id, limit=6)

        # Format duration
        dur = video_obj.duration_seconds or 0
        if dur:
            hours = dur // 3600
            minutes = (dur % 3600) // 60
            seconds = dur % 60
            if hours:
                duration_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                duration_formatted = f"{minutes}:{seconds:02d}"
        else:
            duration_formatted = None

        page_data = {
            "content": content,
            "video": video_obj,
            "yt_comments": yt_comments,
            "related": [serialize_content_card(r) for r in related_items],
            "duration_formatted": duration_formatted,
            "section_slug": content.section.slug if content.section else None,
            "section_name": content.section.name if content.section else None,
            "category_slug": content.category.slug if content.category else None,
            "category_name": content.category.name if content.category else None,
        }
        cache.set(cache_key, page_data, timeout=CACHE_TTL_CONTENT_PAGE)

    _record_view(content_id)
    user_state = _user_state(content_id)

    content = page_data["content"]
    content.section_slug = page_data.get("section_slug")
    content.section_name = page_data.get("section_name")
    content.category_slug = page_data.get("category_slug")
    content.category_name = page_data.get("category_name")

    return render_template(
        "public/video.html",
        content=content,
        video=page_data["video"],
        yt_comments=page_data["yt_comments"],
        related_items=page_data["related"],
        duration_formatted=page_data["duration_formatted"],
        user_state=user_state,
    )


# ─── Search ───────────────────────────────────────────────────────────────────
@public_bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    content_type = request.args.get("type")
    sort = request.args.get("sort", "relevance")

    items = []
    total = 0
    total_pages = 1

    if q and len(q) >= 2:
        cache_key = f"search:unified:v1:{q.lower()}:{content_type or 'all'}:{sort}:{page}"
        cached = cache.get(cache_key)

        if cached is None:
            pagination_obj = SearchRepository.full_text_search(
                query=q,
                object_type=content_type or None,
                sort=sort,
                page=page,
                per_page=24,
            )
            items = [serialize_content_card(c) for c in pagination_obj.items]
            total = pagination_obj.total
            total_pages = pagination_obj.pages
            cached = {"items": items, "total": total, "pages": total_pages}
            cache.set(cache_key, cached, timeout=CACHE_TTL_SEARCH_RESULTS)
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
    )


# ─── Autocomplete API (§11.3) ─────────────────────────────────────────────────
@public_bp.route("/api/search/suggestions")
def search_suggestions():
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
                "url": url_for("public.article", content_id=r.id),
                "thumb": getattr(r, "_article_obj", None).image_url if getattr(r, "_article_obj", None) else None,
                "category": r.category.name if r.category else None,
            }
            for r in results.get("articles", [])
        ],
        "videos": [
            {
                "title": r.title,
                "url": url_for("public.video", content_id=r.id),
                "thumb": getattr(r, "_video_obj", None).thumbnail_url if getattr(r, "_video_obj", None) else None,
                "channel": getattr(r, "_video_obj", None).channel_name if getattr(r, "_video_obj", None) else None,
            }
            for r in results.get("videos", [])
        ],
    }

    cache.set(cache_key, payload, timeout=CACHE_TTL_SEARCH_SUGGESTIONS)
    return jsonify(payload)


# ─── Company & Legal Pages ──────────────────────────────────────────────────
@public_bp.route("/about")
def about():
    """Nexura editorial mission, architecture, and technology overview."""
    return render_template("public/about.html")


@public_bp.route("/contact", methods=["GET", "POST"])
def contact():
    """Contact & editorial tip submission page."""
    submitted = False
    if request.method == "POST":
        # Form processed gracefully; in production could dispatch to an admin inbox / task queue
        submitted = True
    return render_template("public/contact.html", submitted=submitted)


@public_bp.route("/terms")
def terms():
    """Terms of Service and Content Usage Agreement."""
    return render_template("public/terms.html")


@public_bp.route("/privacy")
def privacy():
    """Privacy Policy and Data Protection Disclosure."""
    return render_template("public/privacy.html")

