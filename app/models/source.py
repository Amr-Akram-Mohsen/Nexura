"""Source model representing media outlets, publishers, and channels."""

from __future__ import annotations
from sqlalchemy import Boolean, Column, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from app.extensions import db


class Source(db.Model):
    """Media outlet or publisher profile."""

    __tablename__ = "sources"
    __table_args__ = (Index("ix_sources_slug", "slug"), Index("ix_sources_domain", "domain"), Index("ix_sources_external_uri", "external_uri"))

    id = Column(Integer, primary_key=True)
    external_uri = Column(String(255), unique=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    domain = Column(String(255), nullable=False, unique=True)
    logo_url = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    authority_score = Column(Integer, default=50, nullable=False)

    contents = relationship("Content", back_populates="source")
    article_sources = relationship("ArticleSource", back_populates="source")

    def __repr__(self) -> str:
        return f"<Source {self.slug!r}>"
