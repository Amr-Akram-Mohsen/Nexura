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
    def full_text_search(
        query: str,
        *,
        section_id: int | None = None,
        section_slug: str | None = None,
        category_id: int | None = None,
        category_slug: str | None = None,
        object_type: str | None = None,
        sort: str = "relevance",
        page: int = 1,
        per_page: int = 24,
    ) -> PaginationResult:
        """Unified PostgreSQL full-text search using TSVECTOR, GIN index, and ts_rank_cd."""
        clean = (query or "").strip()
        if not clean:
            items, total = ContentRepository.list_contents(
                section_slug=section_slug,
                category_slug=category_slug,
                object_type=object_type,
                sort="latest" if sort == "relevance" else sort,
                page=page,
                per_page=per_page,
            )
            return PaginationResult(items=items, total=total, page=page, per_page=per_page)

        def _build_base_query():
            q = (
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
                q = q.filter(Content.object_type == object_type)

            if section_id:
                q = q.filter(Content.section_id == section_id)
            elif section_slug:
                q = q.join(Content.section).filter(Section.slug == section_slug)

            if category_id:
                q = q.filter(Content.category_id == category_id)
            elif category_slug:
                q = q.join(Content.category).filter(Category.slug == category_slug)

            return q

        # 1. Primary: PostgreSQL full-text search with plainto_tsquery and ts_rank_cd
        tsquery = func.plainto_tsquery("english", clean)
        rank_expr = func.ts_rank_cd(Content.search_vector, tsquery).label("rank")

        fts_query = _build_base_query().filter(Content.search_vector.op("@@")(tsquery))
        total = fts_query.with_entities(func.count(func.distinct(Content.id))).scalar() or 0

        target_query = fts_query
        is_fts = True

        # 2. Fallback: If FTS matches 0 rows (e.g. stop words, symbols, or unindexed terms), fallback to ILIKE
        if total == 0:
            clean_sub = re.sub(r"[^\w\s]", " ", clean).strip()
            if clean_sub:
                pattern = f"%{clean_sub}%"
                ilike_query = _build_base_query().filter(
                    or_(
                        Content.title.ilike(pattern),
                        Content.preview_text.ilike(pattern),
                        Content.search_text.ilike(pattern),
                    )
                )
                total = ilike_query.with_entities(func.count(func.distinct(Content.id))).scalar() or 0
                target_query = ilike_query
                is_fts = False

        if sort == "popular":
            target_query = target_query.order_by(desc(Content.view_count), desc(Content.published_at))
        elif sort == "score":
            target_query = target_query.order_by(desc(Content.score), desc(Content.published_at))
        elif sort == "latest":
            target_query = target_query.order_by(desc(Content.published_at))
        else:  # relevance
            if is_fts:
                target_query = target_query.order_by(desc(rank_expr), desc(Content.published_at))
            else:
                target_query = target_query.order_by(desc(Content.score), desc(Content.published_at))

        offset = max(0, (page - 1) * per_page)
        contents = target_query.offset(offset).limit(per_page).all()
        resolved = ContentRepository.resolve_polymorphic_payloads(contents)

        return PaginationResult(items=resolved, total=total, page=page, per_page=per_page)

    @staticmethod
    def search(
        query_text: str,
        *,
        section_id: int | None = None,
        section_slug: str | None = None,
        category_id: int | None = None,
        category_slug: str | None = None,
        object_type: str | None = None,
        sort: str = "relevance",
        page: int = 1,
        per_page: int = 24,
    ) -> tuple[list[Content], int]:
        """Execute unified search returning (items, total) tuple."""
        res = SearchRepository.full_text_search(
            query=query_text,
            section_id=section_id,
            section_slug=section_slug,
            category_id=category_id,
            category_slug=category_slug,
            object_type=object_type,
            sort=sort,
            page=page,
            per_page=per_page,
        )
        return res.items, res.total

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
