"""
Nexura Phase 7 — Content Repository
Authoritative query layer for master contents.
Enforces eager loading invariants (joinedload on single relations, selectinload on collections)
and polymorphic batch resolution (2 queries total for batch article/video payloads).
"""
from __future__ import annotations
from typing import Sequence
from datetime import datetime, timezone

from sqlalchemy import desc, asc, func, and_, or_
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models.content import Content, Article, ArticleSource, Author, ContentEntity, ContentLocation
from app.models.video import Video
from app.models.taxonomy import Section, Category, Entity, IntentFacet, GenderFacet, PriceTierFacet
from app.models.source import Source


class ContentRepository:
    """Repository for querying, listing, and resolving polymorphic Content aggregates."""

    @staticmethod
    def get_by_id(content_id: int, *, published_only: bool = True) -> Content | None:
        """Fetch single Content with base relations eager-loaded."""
        query = (
            db.session.query(Content)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                joinedload(Content.intent_facet),
                joinedload(Content.gender_facet),
                joinedload(Content.price_tier_facet),
                selectinload(Content.content_entities).joinedload(ContentEntity.entity),
                selectinload(Content.content_locations).joinedload(ContentLocation.location),
            )
            .filter(Content.id == content_id)
        )
        if published_only:
            query = query.filter(Content.is_active.is_(True), Content.is_published.is_(True))
        return query.first()

    @staticmethod
    def resolve_polymorphic_payloads(contents: Sequence[Content]) -> list[Content]:
        """
        Polymorphic batch resolver (Phase 7 §25.1).
        Resolves underlying Article and Video objects in exactly 2 batch queries.
        Attaches _article_obj or _video_obj to each Content instance.
        """
        if not contents:
            return []

        article_ids = [c.object_id for c in contents if c.object_type == "article"]
        video_ids = [c.object_id for c in contents if c.object_type == "video"]

        articles_by_id: dict[int, Article] = {}
        if article_ids:
            articles = (
                db.session.query(Article)
                .options(
                    selectinload(Article.authors),
                    selectinload(Article.article_sources).joinedload(ArticleSource.source),
                )
                .filter(Article.id.in_(article_ids))
                .all()
            )
            articles_by_id = {a.id: a for a in articles}

        videos_by_id: dict[int, Video] = {}
        if video_ids:
            videos = (
                db.session.query(Video)
                .options(
                    selectinload(Video.video_comments),
                )
                .filter(Video.id.in_(video_ids))
                .all()
            )
            videos_by_id = {v.id: v for v in videos}

        for c in contents:
            if c.object_type == "article":
                setattr(c, "_article_obj", articles_by_id.get(c.object_id))
            elif c.object_type == "video":
                setattr(c, "_video_obj", videos_by_id.get(c.object_id))

        return list(contents)

    @staticmethod
    def list_contents(
        *,
        section_slug: str | None = None,
        category_slug: str | None = None,
        entity_slug: str | None = None,
        source_slug: str | None = None,
        intent_slug: str | None = None,
        gender_slug: str | None = None,
        price_tier_slug: str | None = None,
        object_type: str | None = None,
        sort: str = "latest",
        page: int = 1,
        per_page: int = 24,
        published_only: bool = True,
    ) -> tuple[list[Content], int]:
        """
        Query contents with multi-faceted filtering, sorting, pagination,
        and eager loading to prevent N+1 queries.
        Returns (resolved_contents, total_count).
        """
        query = db.session.query(Content).options(
            joinedload(Content.section),
            joinedload(Content.category),
            joinedload(Content.source),
            joinedload(Content.intent_facet),
            joinedload(Content.gender_facet),
            joinedload(Content.price_tier_facet),
            selectinload(Content.content_entities).joinedload(ContentEntity.entity),
        )

        if published_only:
            query = query.filter(Content.is_active.is_(True), Content.is_published.is_(True))

        if object_type in ("article", "video"):
            query = query.filter(Content.object_type == object_type)

        if section_slug:
            query = query.join(Content.section).filter(Section.slug == section_slug)

        if category_slug:
            query = query.join(Content.category).filter(Category.slug == category_slug)

        if entity_slug:
            query = (
                query.join(Content.content_entities)
                .join(ContentEntity.entity)
                .filter(Entity.slug == entity_slug)
            )

        if source_slug:
            query = query.join(Content.source).filter(Source.slug == source_slug)

        if intent_slug:
            query = query.join(Content.intent_facet).filter(IntentFacet.slug == intent_slug)

        if gender_slug:
            query = query.join(Content.gender_facet).filter(GenderFacet.slug == gender_slug)

        if price_tier_slug:
            query = query.join(Content.price_tier_facet).filter(PriceTierFacet.slug == price_tier_slug)

        # Count total matching before pagination
        total = query.with_entities(func.count(func.distinct(Content.id))).scalar() or 0

        # Sorting strategy
        if sort == "popular":
            query = query.order_by(desc(Content.view_count), desc(Content.published_at))
        elif sort == "score":
            query = query.order_by(desc(Content.score), desc(Content.published_at))
        elif sort == "top_reviewed":
            query = query.order_by(desc(Content.review_score), desc(Content.review_count))
        else:  # "latest" (default)
            query = query.order_by(desc(Content.published_at), desc(Content.id))

        offset = max(0, (page - 1) * per_page)
        contents = query.offset(offset).limit(per_page).all()

        # Batch resolve polymorphic payloads
        resolved = ContentRepository.resolve_polymorphic_payloads(contents)
        return resolved, total

    @staticmethod
    def get_featured_hero(*, section_slug: str | None = None) -> Content | None:
        """Fetch the top scoring featured content for homepage or section hero banner."""
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
        if section_slug:
            query = query.join(Content.section).filter(Section.slug == section_slug)

        # Top score within recent published items
        hero = query.order_by(desc(Content.score), desc(Content.published_at)).first()
        if hero:
            ContentRepository.resolve_polymorphic_payloads([hero])
        return hero

    @staticmethod
    def get_trending(limit: int = 6, *, section_id: int | None = None) -> list[Content]:
        """Fetch trending contents based on view counts and engagement."""
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
        if section_id:
            query = query.filter(Content.section_id == section_id)

        items = query.order_by(desc(Content.view_count), desc(Content.published_at)).limit(limit).all()
        return ContentRepository.resolve_polymorphic_payloads(items)

    @staticmethod
    def get_related(content: Content, limit: int = 6) -> list[Content]:
        """
        Fetch related contents based on matching category and shared entities,
        excluding the given content itself.
        """
        entity_ids = [ce.entity_id for ce in content.content_entities if ce.entity_id]

        query = (
            db.session.query(Content)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                selectinload(Content.content_entities).joinedload(ContentEntity.entity),
            )
            .filter(
                Content.id != content.id,
                Content.is_active.is_(True),
                Content.is_published.is_(True),
            )
        )

        conditions = []
        if content.category_id:
            conditions.append(Content.category_id == content.category_id)
        if entity_ids:
            conditions.append(
                Content.id.in_(
                    db.session.query(ContentEntity.content_id)
                    .filter(ContentEntity.entity_id.in_(entity_ids))
                    .scalar_subquery()
                )
            )

        if conditions:
            query = query.filter(or_(*conditions))

        items = query.order_by(desc(Content.published_at)).limit(limit).all()
        return ContentRepository.resolve_polymorphic_payloads(items)

    @staticmethod
    def get_hero_items(limit: int = 5) -> list[Content]:
        """Fetch top hero carousel items."""
        query = (
            db.session.query(Content)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                selectinload(Content.content_entities).joinedload(ContentEntity.entity),
            )
            .filter(Content.is_active.is_(True), Content.is_published.is_(True))
            .order_by(desc(Content.score), desc(Content.view_count), desc(Content.published_at))
            .limit(limit)
        )
        return ContentRepository.resolve_polymorphic_payloads(query.all())

    @staticmethod
    def list_published(
        *,
        section_id: int | None = None,
        category_id: int | None = None,
        object_type: str | None = None,
        page: int = 1,
        per_page: int = 24,
    ) -> PaginationResult:
        """List published contents returning pagination object with .items, .total, .pages."""
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
        if section_id:
            query = query.filter(Content.section_id == section_id)
        if category_id:
            query = query.filter(Content.category_id == category_id)
        if object_type in ("article", "video"):
            query = query.filter(Content.object_type == object_type)

        total = query.with_entities(func.count(func.distinct(Content.id))).scalar() or 0
        offset = max(0, (page - 1) * per_page)
        items = query.order_by(desc(Content.published_at)).offset(offset).limit(per_page).all()
        resolved = ContentRepository.resolve_polymorphic_payloads(items)
        return PaginationResult(items=resolved, total=total, page=page, per_page=per_page)

    @staticmethod
    def list_by_entity(
        *,
        entity_id: int,
        object_type: str | None = None,
        page: int = 1,
        per_page: int = 24,
    ) -> PaginationResult:
        """List contents tagged with a specific entity."""
        query = (
            db.session.query(Content)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                selectinload(Content.content_entities).joinedload(ContentEntity.entity),
            )
            .join(Content.content_entities)
            .filter(
                ContentEntity.entity_id == entity_id,
                Content.is_active.is_(True),
                Content.is_published.is_(True),
            )
        )
        if object_type in ("article", "video"):
            query = query.filter(Content.object_type == object_type)

        total = query.with_entities(func.count(func.distinct(Content.id))).scalar() or 0
        offset = max(0, (page - 1) * per_page)
        items = query.order_by(desc(Content.published_at)).offset(offset).limit(per_page).all()
        resolved = ContentRepository.resolve_polymorphic_payloads(items)
        return PaginationResult(items=resolved, total=total, page=page, per_page=per_page)

    @staticmethod
    def get_published_content(content_id: int) -> Content | None:
        """Alias for get_by_id with published_only=True."""
        return ContentRepository.get_by_id(content_id, published_only=True)

    @staticmethod
    def get_entities_for_content(content_id: int) -> list[Entity]:
        """Fetch linked Entity records for a content item."""
        links = (
            db.session.query(ContentEntity)
            .options(joinedload(ContentEntity.entity))
            .filter(ContentEntity.content_id == content_id)
            .all()
        )
        return [link.entity for link in links if link.entity]

    @staticmethod
    def get_related_content(content_id: int, limit: int = 6) -> list[Content]:
        """Fetch related content by content_id."""
        content = ContentRepository.get_by_id(content_id, published_only=True)
        if not content:
            return []
        return ContentRepository.get_related(content, limit=limit)


class PaginationResult:
    """Lightweight pagination container matching Flask-SQLAlchemy Pagination interface."""

    def __init__(self, items: list[Any], total: int, page: int, per_page: int):
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page
        self.pages = max(1, (total + per_page - 1) // per_page) if per_page else 1
