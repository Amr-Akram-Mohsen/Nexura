"""Search repository for full-text search queries and autocomplete suggestions."""

from __future__ import annotations
from typing import Any
import re

from sqlalchemy import desc, func, text, and_, or_
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models.content import Content, ContentEntity
from app.models.taxonomy import Category, Entity, Section
from app.repositories.content_repo import ContentRepository, PaginationResult


class SearchRepository:
    """Multi-component search engine and autocomplete index."""

    @staticmethod
    def search(
        query_text: str,
        *,
        section_slug: str | None = None,
        category_slug: str | None = None,
        object_type: str | None = None,
        sort: str = "relevance",
        page: int = 1,
        per_page: int = 24,
    ) -> tuple[list[Content], int]:
        """Execute unified search using title and preview matching with scoring and filters."""
        if not query_text or not query_text.strip():
            return ContentRepository.list_contents(
                section_slug=section_slug,
                category_slug=category_slug,
                object_type=object_type,
                sort="latest" if sort == "relevance" else sort,
                page=page,
                per_page=per_page,
            )

        clean_query = re.sub(r"[^\w\s]", " ", query_text).strip()
        if not clean_query:
            return [], 0

        query = (
            db.session.query(Content)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                selectinload(Content.content_entities).joinedload(ContentEntity.entity),
            )
            .filter(Content.is_active.is_(True), Content.is_published.is_(True))
        )

        if object_type in ("article", "video"):
            query = query.filter(Content.object_type == object_type)

        if section_slug:
            query = query.join(Content.section).filter(Section.slug == section_slug)

        if category_slug:
            query = query.join(Content.category).filter(Category.slug == category_slug)

        title_match = Content.title.ilike(f"%{clean_query}%")
        query = query.filter(title_match)

        total = query.with_entities(func.count(func.distinct(Content.id))).scalar() or 0

        if sort == "popular":
            query = query.order_by(desc(Content.view_count), desc(Content.published_at))
        elif sort == "score":
            query = query.order_by(desc(Content.score), desc(Content.published_at))
        else:
            query = query.order_by(desc(Content.published_at))

        offset = max(0, (page - 1) * per_page)
        contents = query.offset(offset).limit(per_page).all()

        resolved = ContentRepository.resolve_polymorphic_payloads(contents)
        return resolved, total

    @staticmethod
    def full_text_search(
        query: str,
        *,
        section_slug: str | None = None,
        category_slug: str | None = None,
        object_type: str | None = None,
        sort: str = "relevance",
        page: int = 1,
        per_page: int = 24,
    ) -> PaginationResult:
        """Alias for search returning PaginationResult."""
        contents, total = SearchRepository.search(
            query, section_slug=section_slug, category_slug=category_slug, object_type=object_type, sort=sort, page=page, per_page=per_page
        )
        return PaginationResult(items=contents, total=total, page=page, per_page=per_page)

    @staticmethod
    def autocomplete(query: str, limit: int = 5) -> dict[str, list[Content]]:
        """Autocomplete helper returning articles and videos."""
        pattern = f"%{query.strip()}%"
        articles = (
            db.session.query(Content)
            .options(joinedload(Content.category))
            .filter(Content.object_type == "article", Content.title.ilike(pattern), Content.is_active.is_(True), Content.is_published.is_(True))
            .order_by(desc(Content.published_at))
            .limit(limit)
            .all()
        )
        videos = (
            db.session.query(Content)
            .options(joinedload(Content.category))
            .filter(Content.object_type == "video", Content.title.ilike(pattern), Content.is_active.is_(True), Content.is_published.is_(True))
            .order_by(desc(Content.published_at))
            .limit(limit)
            .all()
        )
        ContentRepository.resolve_polymorphic_payloads(articles)
        ContentRepository.resolve_polymorphic_payloads(videos)
        return {"articles": articles, "videos": videos}

    @staticmethod
    def autocomplete_suggestions(query_text: str, limit: int = 8) -> list[dict[str, Any]]:
        """Instant autocomplete suggestions aggregating entities, categories, and titles."""
        if not query_text or len(query_text.strip()) < 2:
            return []

        clean = query_text.strip()
        pattern = f"%{clean}%"
        suggestions: list[dict[str, Any]] = []

        entities = db.session.query(Entity).filter(Entity.name.ilike(pattern)).order_by(Entity.name.asc()).limit(4).all()
        for e in entities:
            suggestions.append(
                {
                    "type": "entity",
                    "label": e.name,
                    "sublabel": e.entity_type.capitalize() if e.entity_type else "Topic",
                    "url": f"/topic/{e.slug}",
                    "slug": e.slug,
                }
            )

        categories = db.session.query(Category).filter(Category.name.ilike(pattern), Category.is_active.is_(True)).order_by(Category.name.asc()).limit(3).all()
        for cat in categories:
            suggestions.append({"type": "category", "label": cat.name, "sublabel": "Category", "url": f"/category/{cat.slug}", "slug": cat.slug})

        remaining_slots = limit - len(suggestions)
        if remaining_slots > 0:
            contents = (
                db.session.query(Content.id, Content.title, Content.object_type)
                .filter(Content.title.ilike(pattern), Content.is_active.is_(True), Content.is_published.is_(True))
                .order_by(desc(Content.published_at))
                .limit(remaining_slots)
                .all()
            )
            from app.utils.slugify import make_slug

            for c in contents:
                slug = make_slug(c.title or "", max_length=100) or ""
                slug_id = f"{c.id}-{slug}" if slug else str(c.id)
                url = f"/{c.object_type}/{slug_id}"
                suggestions.append({"type": "content", "label": c.title, "sublabel": c.object_type.capitalize(), "url": url, "id": c.id})

        return suggestions[:limit]
