"""
Nexura Phase 7 â€” Multichannel Content Syndication
Covers: DistributionPlatform, DistributionPost
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean, Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.extensions import db


class DistributionPlatform(db.Model):
    """Social platform available for content syndication."""
    __tablename__ = "distribution_platforms"

    id = Column(Integer, primary_key=True)
    # 'youtube', 'pinterest', 'instagram', 'facebook', 'tiktok'
    name = Column(String(50), nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")

    posts = relationship("DistributionPost", back_populates="platform")

    def __repr__(self) -> str:
        return f"<DistributionPlatform {self.name!r}>"


class DistributionPost(db.Model):
    """Editorial social post draft/scheduled post for a content item."""
    __tablename__ = "distribution_posts"
    __table_args__ = (
        Index("ix_distribution_posts_content", "content_id"),
        Index("ix_distribution_posts_status", "status"),
        Index("ix_distribution_posts_publish_date", "publish_date"),
    )

    id = Column(Integer, primary_key=True)
    platform_id = Column(
        Integer, ForeignKey("distribution_platforms.id", ondelete="CASCADE"), nullable=False
    )
    content_id = Column(
        Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False
    )
    # 'draft', 'scheduled', 'published'
    status = Column(String(20), default="draft", nullable=False)
    platform_specific_text = Column(Text)
    external_url = Column(Text)
    publish_date = Column(TIMESTAMP(timezone=True))
    views_count = Column(Integer, default=0, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    clicks_count = Column(Integer, default=0, nullable=False)
    shares_count = Column(Integer, default=0, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")
    updated_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")

    platform = relationship("DistributionPlatform", back_populates="posts")
    content = relationship("Content", back_populates="distribution_posts")

    @property
    def engagement_index(self) -> float:
        """Platform Engagement Index: 2*Likes + 5*Clicks + 10*Shares + 0.1*Views"""
        return (
            2.0 * self.likes_count
            + 5.0 * self.clicks_count
            + 10.0 * self.shares_count
            + 0.1 * self.views_count
        )

    def __repr__(self) -> str:
        return f"<DistributionPost {self.id} status={self.status!r}>"
