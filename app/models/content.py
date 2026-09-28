"""Master Content model and associated content metadata entities."""

from __future__ import annotations
from sqlalchemy import and_, Boolean, CheckConstraint, Column, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, TIMESTAMP
from sqlalchemy.orm import foreign, relationship

from app.extensions import db
from app.models.author import Author, article_authors
from app.models.article import Article, ArticleSource, article_categories


class Content(db.Model):
    """Master content aggregator and public entry point for articles and videos."""

    __tablename__ = "contents"
    __table_args__ = (
        UniqueConstraint("object_type", "object_id", name="uq_contents_object_type_id"),
        CheckConstraint("object_type IN ('article', 'video')", name="ck_contents_object_type_valid"),
        Index("ix_contents_published_at", "published_at"),
        Index("ix_contents_active", "is_active"),
        Index("ix_contents_view_count", "view_count"),
        Index("ix_contents_score", "score"),
        Index("ix_contents_review_score", "review_score"),
        Index("ix_contents_review_count", "review_count"),
        Index("ix_contents_section_id", "section_id"),
        Index("ix_contents_category_id", "category_id"),
        Index("ix_contents_category_published_at", "category_id", "published_at"),
        Index("ix_contents_section_published_at", "section_id", "published_at"),
        Index("ix_contents_active_published_at", "is_active", "published_at"),
        Index("ix_contents_title", "title"),
        Index("ix_contents_search_vector", "search_vector", postgresql_using="gin"),
    )

    id = Column(Integer, primary_key=True)
    object_type = Column(String(20), nullable=False)
    object_id = Column(Integer, nullable=False)
    published_at = Column(TIMESTAMP(timezone=True), nullable=False)
    ingested_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")
    title = Column(Text)
    preview_text = Column(Text)
    search_text = Column(Text)
    search_vector = Column(TSVECTOR)
    is_active = Column(Boolean, default=True, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)

    like_count = Column(Integer, default=0, nullable=False)
    dislike_count = Column(Integer, default=0, nullable=False)
    share_count = Column(Integer, default=0, nullable=False)
    save_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)

    score = Column(Float, default=0.0, nullable=False)
    review_score = Column(Float, default=0.0, nullable=False)
    review_count = Column(Integer, default=0, nullable=False)

    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))
    section_id = Column(Integer, ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False)
    gender_id = Column(Integer, ForeignKey("gender_facets.id", ondelete="SET NULL"))
    intent_id = Column(Integer, ForeignKey("intent_facets.id", ondelete="SET NULL"))
    price_tier_id = Column(Integer, ForeignKey("price_tier_facets.id", ondelete="SET NULL"))
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"))

    ingestion_origin = Column(String(50))

    section = relationship("Section", back_populates="contents")
    category = relationship("Category", back_populates="contents")
    source = relationship("Source", back_populates="contents")
    intent_facet = relationship("IntentFacet", back_populates="contents")
    gender_facet = relationship("GenderFacet", back_populates="contents")
    price_tier_facet = relationship("PriceTierFacet", back_populates="contents")
    content_entities = relationship("ContentEntity", back_populates="content", cascade="all, delete-orphan")
    content_locations = relationship("ContentLocation", back_populates="content", cascade="all, delete-orphan")
    views = relationship("View", back_populates="content", cascade="all, delete-orphan")
    saves = relationship("Save", back_populates="content", cascade="all, delete-orphan")
    reactions = relationship(
        "Reaction",
        primaryjoin="and_(Content.id == foreign(Reaction.target_id), Reaction.target_type == 'content')",
        cascade="all, delete-orphan",
        overlaps="user",
    )
    comments = relationship("Comment", back_populates="content_ref", cascade="all, delete-orphan")
    shares = relationship("Share", back_populates="content", cascade="all, delete-orphan")
    user_interests = relationship("UserInterest", back_populates="content", cascade="all, delete-orphan")
    distribution_posts = relationship("DistributionPost", back_populates="content", cascade="all, delete-orphan")

    @property
    def slug(self) -> str:
        from app.utils.slugify import make_slug

        return make_slug(self.title or "", max_length=100) or ""

    @property
    def slug_id(self) -> str:
        s = self.slug
        return f"{self.id}-{s}" if s else str(self.id)

    @property
    def url(self) -> str:
        return f"/{self.object_type}/{self.slug_id}"

    def __repr__(self) -> str:
        return f"<Content {self.id} {self.object_type}/{self.object_id}>"


class ContentEntity(db.Model):
    """Many-to-many relationship between content and extracted taxonomy entities."""

    __tablename__ = "content_entities"
    __table_args__ = (Index("ix_content_entities_entity_content", "entity_id", "content_id"),)

    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    relevance_score = Column(Float, default=0.0)
    origin = Column(String(30))
    confidence = Column(Float)

    content = relationship("Content", back_populates="content_entities")
    entity = relationship("Entity", back_populates="content_entities")


class ContentLocation(db.Model):
    """Many-to-many relationship between content and geographical locations."""

    __tablename__ = "content_locations"
    __table_args__ = (Index("ix_content_locations_location", "location_id"), Index("ix_content_locations_content", "content_id"))

    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True)

    content = relationship("Content", back_populates="content_locations")
    location = relationship("Location")


__all__ = ["Content", "ContentEntity", "ContentLocation", "Article", "ArticleSource", "Author", "article_authors", "article_categories"]
