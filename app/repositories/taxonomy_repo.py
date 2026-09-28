"""Taxonomy repository for sections, categories, entities, sources, and facets."""

from __future__ import annotations
from typing import Sequence

from sqlalchemy import desc, asc, func
from sqlalchemy.orm import selectinload, joinedload

from app.extensions import db
from app.models.taxonomy import Section, Category, Entity, Location, Event, IntentFacet, GenderFacet, PriceTierFacet
from app.models.source import Source
from app.models.content import ContentEntity


class TaxonomyRepository:
    """Data access operations for taxonomy and reference data."""

    @staticmethod
    def get_sections(*, active_only: bool = True) -> list[Section]:
        """Fetch all domain sections ordered by sort_order."""
        query = db.session.query(Section)
        if active_only:
            query = query.filter(Section.is_active.is_(True))
        return query.order_by(Section.sort_order.asc(), Section.name.asc()).all()

    @staticmethod
    def get_active_sections() -> list[Section]:
        """Fetch all active domain sections."""
        return TaxonomyRepository.get_sections(active_only=True)

    @staticmethod
    def get_section_by_slug(slug: str) -> Section | None:
        """Fetch section by slug."""
        return db.session.query(Section).filter(Section.slug == slug).first()

    @staticmethod
    def get_categories_for_section(section_id: int, min_items: int = 1, limit: int = 12) -> list[Category]:
        """Fetch active categories with published content in the specified section."""
        from app.models.content import Content

        return (
            db.session.query(Category)
            .join(Content, Content.category_id == Category.id)
            .filter(Content.section_id == section_id, Content.is_published.is_(True), Content.is_active.is_(True), Category.is_active.is_(True))
            .group_by(Category.id)
            .having(func.count(Content.id) >= min_items)
            .order_by(func.count(Content.id).desc(), Category.name.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_subcategories(category_id: int) -> list[Category]:
        """Fetch children subcategories for a category."""
        return (
            db.session.query(Category)
            .filter(Category.parent_id == category_id, Category.is_active.is_(True))
            .order_by(Category.sort_order.asc(), Category.name.asc())
            .all()
        )

    @staticmethod
    def get_categories(*, active_only: bool = True, parent_id: int | None = None, leaf_only: bool = False) -> list[Category]:
        """Fetch categories with optional hierarchy filters."""
        query = db.session.query(Category)
        if active_only:
            query = query.filter(Category.is_active.is_(True))
        if parent_id is not None:
            query = query.filter(Category.parent_id == parent_id)
        if leaf_only:
            query = query.filter(Category.is_leaf.is_(True))
        return query.order_by(Category.sort_order.asc(), Category.name.asc()).all()

    @staticmethod
    def get_category_by_slug(slug: str) -> Category | None:
        """Fetch category by slug with parent and children loaded."""
        return db.session.query(Category).options(joinedload(Category.parent), selectinload(Category.children)).filter(Category.slug == slug).first()

    @staticmethod
    def get_entity_by_slug(slug: str) -> Entity | None:
        """Fetch entity by slug."""
        return db.session.query(Entity).filter(Entity.slug == slug).first()

    @staticmethod
    def get_entity_by_id(entity_id: int) -> Entity | None:
        """Fetch entity by ID."""
        return db.session.query(Entity).filter(Entity.id == entity_id).first()

    @staticmethod
    def get_entities_by_type(entity_type: str, limit: int = 50) -> list[Entity]:
        """Fetch entities filtered by entity type."""
        return db.session.query(Entity).filter(Entity.entity_type == entity_type).order_by(Entity.name.asc()).limit(limit).all()

    @staticmethod
    def get_popular_entities(*, entity_type: str | None = None, limit: int = 20) -> list[tuple[Entity, int]]:
        """Fetch top entities ranked by frequency of content associations."""
        query = (
            db.session.query(Entity, func.count(ContentEntity.content_id).label("content_count"))
            .join(ContentEntity, ContentEntity.entity_id == Entity.id)
            .group_by(Entity.id)
        )
        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)

        results = query.order_by(desc("content_count")).limit(limit).all()
        return [(r[0], r[1]) for r in results]

    @staticmethod
    def get_trending_entities(limit: int = 20) -> list[Entity]:
        """Fetch trending entities as a list of Entity records."""
        popular = TaxonomyRepository.get_popular_entities(limit=limit)
        if popular:
            return [p[0] for p in popular]
        return db.session.query(Entity).order_by(Entity.name.asc()).limit(limit).all()

    @staticmethod
    def get_related_entities(entity_id: int, limit: int = 10) -> list[Entity]:
        """Fetch related entities that co-occur in content with this entity."""
        shared_content_subq = db.session.query(ContentEntity.content_id).filter(ContentEntity.entity_id == entity_id).scalar_subquery()
        related = (
            db.session.query(Entity)
            .join(ContentEntity, ContentEntity.entity_id == Entity.id)
            .filter(ContentEntity.content_id.in_(shared_content_subq), Entity.id != entity_id)
            .group_by(Entity.id)
            .order_by(func.count(ContentEntity.content_id).desc())
            .limit(limit)
            .all()
        )
        return related

    @staticmethod
    def merge_entities(source_entity_id: int, target_entity_id: int) -> int:
        """Merge source entity into target entity, re-pointing all associations and deleting source."""
        if source_entity_id == target_entity_id:
            return 0

        target_content_ids = {r[0] for r in db.session.query(ContentEntity.content_id).filter(ContentEntity.entity_id == target_entity_id).all()}

        source_links = db.session.query(ContentEntity).filter(ContentEntity.entity_id == source_entity_id).all()

        moved_count = 0
        for link in source_links:
            if link.content_id not in target_content_ids:
                link.entity_id = target_entity_id
                moved_count += 1
            else:
                db.session.delete(link)

        source_entity = db.session.get(Entity, source_entity_id)
        if source_entity:
            db.session.delete(source_entity)

        db.session.commit()
        return moved_count

    @staticmethod
    def get_sources(*, active_only: bool = True) -> list[Source]:
        """Fetch media publishers ordered by authority score."""
        query = db.session.query(Source)
        if active_only:
            query = query.filter(Source.is_active.is_(True))
        return query.order_by(desc(Source.authority_score), Source.name.asc()).all()

    @staticmethod
    def get_source_by_slug(slug: str) -> Source | None:
        """Fetch media publisher source by slug."""
        return db.session.query(Source).filter(Source.slug == slug).first()

    @staticmethod
    def get_facets() -> dict[str, list]:
        """Fetch editorial facets for filter menus."""
        return {
            "intents": db.session.query(IntentFacet).order_by(IntentFacet.name.asc()).all(),
            "genders": db.session.query(GenderFacet).order_by(GenderFacet.name.asc()).all(),
            "price_tiers": db.session.query(PriceTierFacet).order_by(PriceTierFacet.name.asc()).all(),
        }
