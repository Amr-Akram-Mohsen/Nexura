"""
Nexura Phase 7 â€” Content, Article, Author, junction tables
Phase 7 Â§4 ownership rules:
  Content   â€” global identity, visibility, engagement counters, taxonomy FKs, search
  Article   â€” extracted body HTML, lifecycle status, media payload
"""
from __future__ import annotations

from sqlalchemy import (
    and_, Boolean, CheckConstraint, Column, Float, ForeignKey, Index, Integer,
    JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, TIMESTAMP
from sqlalchemy.orm import foreign, relationship

from app.extensions import db


# ---------------------------------------------------------------------------
# Junction tables (no model class needed â€” pure association)
# ---------------------------------------------------------------------------

article_authors = db.Table(
    "article_authors",
    Column(
        "article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "author_id", Integer, ForeignKey("authors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_article_authors_author", "author_id"),
    Index("ix_article_authors_article", "article_id"),
)

article_categories = db.Table(
    "article_categories",
    Column(
        "article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("weight", Float, default=0.0, nullable=False),
    Index("ix_article_categories_category", "category_id"),
    Index("ix_article_categories_article", "article_id"),
)


# ---------------------------------------------------------------------------
# Content â€” master aggregator and public entry point
# ---------------------------------------------------------------------------

class Content(db.Model):
    """
    Master content aggregator and public entry point.
    object_type ? {'article', 'video'}; object_id references the specific row.
    """
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
    )

    id = Column(Integer, primary_key=True)
    object_type = Column(String(20), nullable=False)   # 'article' | 'video'
    object_id = Column(Integer, nullable=False)
    published_at = Column(TIMESTAMP(timezone=True), nullable=False)
    ingested_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")
    title = Column(Text)
    preview_text = Column(Text)
    search_text = Column(Text)
    search_vector = Column(TSVECTOR)
    is_active = Column(Boolean, default=True, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)

    # Engagement counters (on-platform â€” distinct from YouTube metrics)
    like_count = Column(Integer, default=0, nullable=False)
    dislike_count = Column(Integer, default=0, nullable=False)
    share_count = Column(Integer, default=0, nullable=False)
    save_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)

    # Scoring cache
    score = Column(Float, default=0.0, nullable=False)
    review_score = Column(Float, default=0.0, nullable=False)
    review_count = Column(Integer, default=0, nullable=False)

    # Taxonomy FKs
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))
    section_id = Column(Integer, ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False)
    gender_id = Column(Integer, ForeignKey("gender_facets.id", ondelete="SET NULL"))
    intent_id = Column(Integer, ForeignKey("intent_facets.id", ondelete="SET NULL"))
    price_tier_id = Column(Integer, ForeignKey("price_tier_facets.id", ondelete="SET NULL"))
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"))

    ingestion_origin = Column(String(50))

    # Relationships
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


# ---------------------------------------------------------------------------
# ContentEntity â€” many-to-many content <-> entity with metadata
# ---------------------------------------------------------------------------

class ContentEntity(db.Model):
    __tablename__ = "content_entities"
    __table_args__ = (
        Index("ix_content_entities_entity_content", "entity_id", "content_id"),
    )

    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    relevance_score = Column(Float, default=0.0)
    origin = Column(String(30))    # 'diffbot', 'rule', 'manual'
    confidence = Column(Float)

    content = relationship("Content", back_populates="content_entities")
    entity = relationship("Entity", back_populates="content_entities")


# ---------------------------------------------------------------------------
# ContentLocation â€” many-to-many content <-> location
# ---------------------------------------------------------------------------

class ContentLocation(db.Model):
    __tablename__ = "content_locations"
    __table_args__ = (
        Index("ix_content_locations_location", "location_id"),
        Index("ix_content_locations_content", "content_id"),
    )

    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True)

    content = relationship("Content", back_populates="content_locations")
    location = relationship("Location")


# ---------------------------------------------------------------------------
# Article â€” written journalism and long-form content
# ---------------------------------------------------------------------------

class Article(db.Model):
    """
    Owns extracted body, lifecycle status, and media payload.
    Phase 7 status values: discovered | enriching | ready | published | failed | archived
    """
    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('discovered', 'enriching', 'ready', 'published', 'failed', 'archived')",
            name="ck_articles_status_valid",
        ),
        Index("ix_articles_status", "status"),
        Index("ix_articles_enrichment_priority", "enrichment_priority"),
        Index("ix_articles_language", "language"),
        Index("ix_articles_sentiment_score", "sentiment_score"),
        Index("ix_articles_canonical_url", "canonical_url"),
    )

    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    summary = Column(Text)
    body = Column(Text)
    content_text = Column(Text)
    content_html = Column(Text)
    word_count = Column(Integer)
    quality_score = Column(Float, default=0.0, nullable=False)
    enrichment_priority = Column(Float, default=0.0, nullable=False)
    ingestion_method = Column(String(50))
    language = Column(String(10))
    sentiment_score = Column(Float)
    extended_metadata = Column(JSON)
    images = Column(JSON)
    videos = Column(JSON)
    status = Column(String(20), default="discovered", nullable=False)
    last_enrichment_attempt = Column(TIMESTAMP(timezone=True))
    image_url = Column(Text)
    canonical_url = Column(String(500))
    event_id = Column(Integer, ForeignKey("events.id", ondelete="SET NULL"))
    # Deferred FK to article_sources (FK set after article_sources table exists)
    primary_source_id = Column(Integer)  # FK: article_sources.id ON DELETE SET NULL

    # Relationships
    event = relationship("Event", back_populates="articles")
    article_sources = relationship("ArticleSource", back_populates="article", cascade="all, delete-orphan",
                                   foreign_keys="ArticleSource.article_id")
    primary_source = relationship(
        "ArticleSource",
        primaryjoin="Article.primary_source_id == ArticleSource.id",
        foreign_keys="Article.primary_source_id",
        uselist=False,
    )
    authors = relationship("Author", secondary=article_authors, back_populates="articles")
    secondary_categories = relationship("Category", secondary=article_categories)

    @property
    def content(self):
        """Resolve the parent Content record via polymorphic lookup."""
        from app.extensions import db
        from app.models.content import Content
        return db.session.query(Content).filter_by(
            object_type="article", object_id=self.id
        ).first()

    def __repr__(self) -> str:
        return f"<Article {self.id} {self.title[:40]!r}>"


# ---------------------------------------------------------------------------
# ArticleSource â€” syndicated URLs across publishers
# ---------------------------------------------------------------------------

class ArticleSource(db.Model):
    __tablename__ = "article_sources"
    __table_args__ = (
        Index("ix_article_sources_published_at", "published_at"),
    )

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False)
    url = Column(Text, nullable=False, unique=True)
    published_at = Column(TIMESTAMP(timezone=True))

    article = relationship("Article", back_populates="article_sources", foreign_keys=[article_id])
    source = relationship("Source", back_populates="article_sources")


# ---------------------------------------------------------------------------
# Author â€” journalists, creators, and curators
# ---------------------------------------------------------------------------

class Author(db.Model):
    __tablename__ = "authors"
    __table_args__ = (
        Index("ix_authors_name", "name"),
        Index("ix_authors_slug", "slug"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True)
    url = Column(Text)
    uri = Column(String(255))
    type = Column(String(50))
    is_agency = Column(Boolean, default=False, nullable=False)
    icon_url = Column(Text)
    aliases = Column(JSON)

    articles = relationship("Article", secondary=article_authors, back_populates="authors")

    def __repr__(self) -> str:
        return f"<Author {self.slug!r}>"
