"""
Nexura Phase 7 â€” Recommendation & Audience Interest Graph
Covers: UserInterest, UserEntityInterest, RecommendationImpression, RecommendationClick
"""
from __future__ import annotations

from sqlalchemy import (
    CheckConstraint, Column, Float, ForeignKey, Index, Integer, JSON,
    String, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.extensions import db


class UserInterest(db.Model):
    """Aggregated user affinity for a specific content item."""
    __tablename__ = "user_interests"
    __table_args__ = (
        UniqueConstraint("user_id", "content_id", name="uq_user_content_interest"),
        Index("ix_user_interest_lookup", "user_id", "content_id"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    interaction_count = Column(Integer, default=0, nullable=False)
    last_interaction_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")

    user = relationship("User", back_populates="user_interests")
    content = relationship("Content", back_populates="user_interests")
    entity_interests = relationship(
        "UserEntityInterest", back_populates="user_interest",
        cascade="all, delete-orphan",
    )


class UserEntityInterest(db.Model):
    """Decomposed interest score by entity or category."""
    __tablename__ = "user_entity_interests"
    __table_args__ = (
        CheckConstraint(
            "entity_id IS NOT NULL OR category_id IS NOT NULL",
            name="ck_user_entity_ref",
        ),
        Index("ix_user_entity_interest_ref", "entity_id", "category_id"),
    )

    id = Column(Integer, primary_key=True)
    user_interest_id = Column(
        Integer, ForeignKey("user_interests.id", ondelete="CASCADE"), nullable=False
    )
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"))
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"))
    score = Column(Float, default=0.0, nullable=False)

    user_interest = relationship("UserInterest", back_populates="entity_interests")
    entity = relationship("Entity")
    category = relationship("Category")


class RecommendationImpression(db.Model):
    """Tracks which content items were shown to a user."""
    __tablename__ = "recommendation_impressions"
    __table_args__ = (
        Index("ix_rec_impressions_created", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False)   # 'content'
    context_id = Column(String(100))
    entity_ids = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    user = relationship("User")


class RecommendationClick(db.Model):
    """Tracks a click on a recommended content item."""
    __tablename__ = "recommendation_clicks"
    __table_args__ = (
        Index("ix_rec_clicks_created", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False)   # 'content'
    entity_id = Column(String(100), nullable=False)
    context_id = Column(String(100))
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    user = relationship("User")
