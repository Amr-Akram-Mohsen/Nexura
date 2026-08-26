"""
Nexura Phase 7 â€” Video & VideoComment Models
Phase 7 Â§4: Videos own external YouTube metadata.
contents.view_count/like_count = on-platform engagement.
videos.view_count/like_count   = external YouTube statistics.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger, CheckConstraint, Column, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import relationship

from app.extensions import db


class Video(db.Model):
    """Streaming and visual media â€” YouTube videos."""
    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint("external_id", "platform", name="uq_videos_external_platform"),
        Index("ix_videos_platform_published", "platform", "published_at"),
        Index("ix_videos_platform_creator", "platform", "creator"),
    )

    id = Column(Integer, primary_key=True)
    external_id = Column(String(100), nullable=False)
    platform = Column(String(50), default="youtube", nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    description_display_rule = Column(String(20), default="review", nullable=False)
    thumbnail_url = Column(Text)
    channel_name = Column(String(150))
    channel_id = Column(String(100))    # Phase 7 addition â€” may require migration
    url = Column(Text)
    creator = Column(String(150))
    published_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")
    duration_seconds = Column(Integer)

    # External YouTube metrics (NOT on-platform engagement)
    view_count = Column(BigInteger, default=0, nullable=False)
    like_count = Column(BigInteger, default=0, nullable=False)
    comments_count = Column(Integer, default=0, nullable=False)

    platform_metadata = Column(JSONB)

    # Relationships
    video_comments = relationship(
        "VideoComment", back_populates="video",
        cascade="all, delete-orphan",
        order_by="VideoComment.like_count.desc()",
    )

    @property
    def content(self):
        """Resolve the parent Content record via polymorphic lookup."""
        from app.extensions import db as _db
        from app.models.content import Content
        return _db.session.query(Content).filter_by(
            object_type="video", object_id=self.id
        ).first()

    def __repr__(self) -> str:
        return f"<Video {self.external_id!r} platform={self.platform!r}>"


class VideoComment(db.Model):
    """Top YouTube comments synced for a video."""
    __tablename__ = "video_comments"
    __table_args__ = (
        Index("ix_video_comments_external_id", "external_id"),
        Index("ix_video_comments_published_at", "published_at"),
    )

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String(100), nullable=False, unique=True)
    author_name = Column(String(150))
    author_channel_id = Column(String(100))
    text = Column(Text, nullable=False)
    like_count = Column(Integer, default=0, nullable=False)
    reply_count = Column(Integer, default=0, nullable=False)
    published_at = Column(TIMESTAMP(timezone=True))
    updated_at = Column(TIMESTAMP(timezone=True))

    video = relationship("Video", back_populates="video_comments")

    def __repr__(self) -> str:
        return f"<VideoComment {self.external_id!r}>"
