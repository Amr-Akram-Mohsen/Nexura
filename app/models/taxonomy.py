"""Taxonomy models: Section, Category, Entity, Location, Facets, and Event."""

from __future__ import annotations
from sqlalchemy import Boolean, Column, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.extensions import db


class Section(db.Model):
    """High-level domain partition (e.g. Technology, Lifestyle)."""

    __tablename__ = "sections"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(120), nullable=False, unique=True, index=True)
    description = Column(Text)
    allowed_filters = Column(JSON)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    contents = relationship("Content", back_populates="section", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Section {self.slug!r}>"


class Category(db.Model):
    """Hierarchical topic cluster."""

    __tablename__ = "categories"
    __table_args__ = (
        Index("ix_categories_slug", "slug"),
        Index("ix_categories_external_uri", "external_uri"),
        Index("ix_categories_normalized_name", "normalized_name"),
        Index("ix_categories_is_leaf", "is_leaf"),
    )

    id = Column(Integer, primary_key=True)
    external_uri = Column(String(255), unique=True)
    name = Column(String(255), nullable=False)
    normalized_name = Column(String(255))
    slug = Column(String(255), nullable=False, unique=True)
    parent_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"))
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_leaf = Column(Boolean, default=True, nullable=False)

    parent = relationship("Category", remote_side="Category.id", back_populates="children")
    children = relationship("Category", back_populates="parent")
    contents = relationship("Content", back_populates="category", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Category {self.slug!r}>"


class Entity(db.Model):
    """Universal named entity: Brand, Topic, Organization, Person, Tag."""

    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_slug", "slug"),
        Index("ix_entities_external_uri", "external_uri"),
        Index("ix_entities_type", "entity_type"),
        Index("ix_entities_wikidata_id", "wikidata_id"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True)
    external_uri = Column(String(255), unique=True)
    entity_type = Column(String(50))
    image_url = Column(Text)
    provider = Column(String(30))
    description = Column(Text)
    aliases = Column(JSON)
    wikidata_id = Column(String(50))
    wikipedia_url = Column(Text)

    content_entities = relationship("ContentEntity", back_populates="entity")

    def __repr__(self) -> str:
        return f"<Entity {self.slug!r} type={self.entity_type!r}>"


class Location(db.Model):
    """Geographic country or region."""

    __tablename__ = "locations"
    __table_args__ = (Index("ix_locations_slug", "slug"), Index("ix_locations_country_code", "country_code"))

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    slug = Column(String(150), nullable=False, unique=True)
    country_code = Column(String(10))
    country_name = Column(String(150))
    latitude = Column(Float)
    longitude = Column(Float)

    def __repr__(self) -> str:
        return f"<Location {self.slug!r}>"


class IntentFacet(db.Model):
    """Editorial intent dimension (e.g. review, news, buying-guide)."""

    __tablename__ = "intent_facets"
    __table_args__ = (UniqueConstraint("name"), UniqueConstraint("slug"))

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, unique=True)
    slug = Column(String(80), nullable=False, unique=True)

    contents = relationship("Content", back_populates="intent_facet")

    def __repr__(self) -> str:
        return f"<IntentFacet {self.slug!r}>"


class GenderFacet(db.Model):
    """Gender audience dimension."""

    __tablename__ = "gender_facets"
    __table_args__ = (UniqueConstraint("name"), UniqueConstraint("slug"))

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    slug = Column(String(50), nullable=False, unique=True)

    contents = relationship("Content", back_populates="gender_facet")

    def __repr__(self) -> str:
        return f"<GenderFacet {self.slug!r}>"


class PriceTierFacet(db.Model):
    """Price tier classification facet."""

    __tablename__ = "price_tier_facets"
    __table_args__ = (UniqueConstraint("name"), UniqueConstraint("slug"))

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    slug = Column(String(50), nullable=False, unique=True)

    contents = relationship("Content", back_populates="price_tier_facet")

    def __repr__(self) -> str:
        return f"<PriceTierFacet {self.slug!r}>"


class Event(db.Model):
    """Scheduled launch or industry event linked to articles."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    event_date = Column(TIMESTAMP(timezone=True))
    external_uri = Column(String(255))
    event_type = Column(String(50))
    summary = Column(Text)
    image_url = Column(Text)

    articles = relationship("Article", back_populates="event")

    def __repr__(self) -> str:
        return f"<Event {self.title!r}>"
