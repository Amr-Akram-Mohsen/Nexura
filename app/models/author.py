"""Author model and article-author association table."""

from __future__ import annotations
from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.extensions import db

article_authors = db.Table(
    "article_authors",
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_article_authors_author", "author_id"),
    Index("ix_article_authors_article", "article_id"),
)


class Author(db.Model):
    """Journalists, creators, and curators."""

    __tablename__ = "authors"
    __table_args__ = (Index("ix_authors_name", "name"), Index("ix_authors_slug", "slug"))

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
