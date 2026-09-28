"""Search service for ranking, full-text queries, and autocomplete."""

from __future__ import annotations
import logging
import math
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models.content import Content, ContentEntity
from app.models.taxonomy import Category, Entity, Section, IntentFacet
from app.repositories.content_repo import ContentRepository, PaginationResult

log = logging.getLogger(__name__)

INTENT_KEYWORDS: dict[str, list[str]] = {
    "buying-guide": ["best", "top", "guide", "buying", "recommendation", "pick", "versus"],
    "review": ["review", "hands-on", "tested", "test", "rating", "verdict", "impressions"],
    "comparison": ["vs", "compare", "comparison", "difference", "better"],
    "tutorial": ["how to", "guide", "setup", "tips", "tutorial", "walkthrough", "fix"],
    "news": ["announce", "launch", "release", "leak", "update", "rumor", "news"],
}


def calculate_search_score(content: Content, query_text: str, now: datetime | None = None) -> float:
    """Compute 4-component search relevance score: text, popularity, freshness, and intent."""
    now_utc = now or datetime.now(timezone.utc)
    clean_query = query_text.strip().lower()
    query_tokens = set(re.findall(r"\w+", clean_query))

    title_lower = (content.title or "").lower()
    preview_lower = (content.preview_text or "").lower()
    entity_names = [ce.entity.name.lower() for ce in (content.content_entities or []) if ce.entity]

    s_text = 0.0
    if clean_query in title_lower:
        s_text += 3.0

    for token in query_tokens:
        if token in title_lower:
            s_text += 1.2
        if token in preview_lower or any(token in ename for ename in entity_names):
            s_text += 0.6

    views = content.view_count or 0
    comments = content.comment_count or 0
    reactions = (content.like_count or 0) + (content.save_count or 0)
    s_pop = math.log(1.0 + views + (comments * 2) + reactions)

    age_days = 0.0
    if content.published_at:
        pub = content.published_at
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now_utc - pub).total_seconds() / 86400.0)

    s_fresh = 0.6 / (1.0 + (age_days / 30.0))

    s_intent = 0.0
    content_intent = content.intent_facet.slug if content.intent_facet else None

    for intent_slug, keywords in INTENT_KEYWORDS.items():
        if any(kw in clean_query for kw in keywords):
            if content_intent == intent_slug or any(kw in title_lower for kw in keywords):
                s_intent += 1.5

    total_score = (4.0 * s_text) + (0.8 * s_pop) + (0.6 * s_fresh) + (1.2 * s_intent)
    return round(total_score, 4)


class SearchService:
    """Unified search engine and autocomplete index."""

    @staticmethod
    def execute_search(
        query_text: str,
        *,
        section_slug: str | None = None,
        category_slug: str | None = None,
        object_type: str | None = None,
        sort: str = "relevance",
        page: int = 1,
        per_page: int = 24,
    ) -> PaginationResult:
        """Execute multi-factor ranked search with faceted filters and pagination."""
        clean_query = query_text.strip()
        if not clean_query:
            return ContentRepository.list_published(object_type=object_type, page=page, per_page=per_page)

        query = (
            db.session.query(Content)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                joinedload(Content.intent_facet),
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

        tokens = re.findall(r"\w+", clean_query)
        match_clauses = [Content.title.ilike(f"%{token}%") for token in tokens]
        match_clauses.append(Content.preview_text.ilike(f"%{clean_query}%"))
        query = query.filter(or_(*match_clauses))

        candidates = query.limit(200).all()
        ContentRepository.resolve_polymorphic_payloads(candidates)

        now = datetime.now(timezone.utc)
        if sort == "popular":
            candidates.sort(key=lambda c: c.view_count or 0, reverse=True)
        elif sort == "recent":
            candidates.sort(key=lambda c: c.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        else:
            candidates.sort(key=lambda c: calculate_search_score(c, clean_query, now=now), reverse=True)

        total = len(candidates)
        offset = max(0, (page - 1) * per_page)
        paged_items = candidates[offset : offset + per_page]

        return PaginationResult(items=paged_items, total=total, page=page, per_page=per_page)

    @staticmethod
    def get_autocomplete_suggestions(query_text: str, limit: int = 8) -> dict[str, Any]:
        """Fetch instant autocomplete suggestions for articles and videos."""
        clean = query_text.strip()
        if len(clean) < 2:
            return {"articles": [], "videos": [], "entities": [], "categories": []}

        pattern = f"%{clean}%"

        articles = (
            db.session.query(Content)
            .options(joinedload(Content.category))
            .filter(Content.object_type == "article", Content.title.ilike(pattern), Content.is_active.is_(True), Content.is_published.is_(True))
            .order_by(desc(Content.published_at))
            .limit(5)
            .all()
        )

        videos = (
            db.session.query(Content)
            .options(joinedload(Content.category))
            .filter(Content.object_type == "video", Content.title.ilike(pattern), Content.is_active.is_(True), Content.is_published.is_(True))
            .order_by(desc(Content.published_at))
            .limit(5)
            .all()
        )

        ContentRepository.resolve_polymorphic_payloads(articles)
        ContentRepository.resolve_polymorphic_payloads(videos)

        return {"articles": articles, "videos": videos}
