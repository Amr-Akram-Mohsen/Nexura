"""Article and ArticleSource models for written journalistic content."""

from __future__ import annotations
from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.author import article_authors

article_categories = db.Table(
    "article_categories",
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
    Column("weight", Float, default=0.0, nullable=False),
    Index("ix_article_categories_category", "category_id"),
    Index("ix_article_categories_article", "article_id"),
)


class Article(db.Model):
    """Article entity owning body content, enrichment metadata, and lifecycle status."""

    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint("status IN ('discovered', 'enriching', 'ready', 'published', 'failed', 'archived')", name="ck_articles_status_valid"),
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
    primary_source_id = Column(Integer)

    event = relationship("Event", back_populates="articles")
    article_sources = relationship("ArticleSource", back_populates="article", cascade="all, delete-orphan", foreign_keys="ArticleSource.article_id")
    primary_source = relationship(
        "ArticleSource", primaryjoin="Article.primary_source_id == ArticleSource.id", foreign_keys="Article.primary_source_id", uselist=False
    )
    authors = relationship("Author", secondary=article_authors, back_populates="articles")
    secondary_categories = relationship("Category", secondary=article_categories)

    @property
    def content(self):
        """Resolve parent Content record via polymorphic lookup."""
        from app.extensions import db as _db
        from app.models.content import Content

        return _db.session.query(Content).filter_by(object_type="article", object_id=self.id).first()

    def __repr__(self) -> str:
        return f"<Article {self.id} {self.title[:40]!r}>"


class ArticleSource(db.Model):
    """Syndicated URLs and publisher sources for an article."""

    __tablename__ = "article_sources"
    __table_args__ = (Index("ix_article_sources_published_at", "published_at"),)

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False)
    url = Column(Text, nullable=False, unique=True)
    published_at = Column(TIMESTAMP(timezone=True))

    article = relationship("Article", back_populates="article_sources", foreign_keys=[article_id])
    source = relationship("Source", back_populates="article_sources")

    def __repr__(self) -> str:
        return f"<ArticleSource {self.id} article_id={self.article_id}>"
