"""
Nexura Phase 7 â€” User Interaction Models
Covers: View, Save, Reaction, Comment (threaded), Share
Phase 7 schema: comments/shares use concrete content_id FK (not polymorphic).
"""
from __future__ import annotations

from sqlalchemy import (
    CheckConstraint, Column, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.extensions import db


class View(db.Model):
    """Content view/read history â€” authenticated or anonymous."""
    __tablename__ = "views"
    __table_args__ = (
        # Partial unique indexes â€” defined via __table_args__ strings for PostgreSQL
        # These match exactly what Phase 7 specifies.
        CheckConstraint(
            "(user_id IS NOT NULL AND ip_address IS NULL) OR (user_id IS NULL AND ip_address IS NOT NULL)",
            name="ck_view_one_identity",
        ),
        Index("ix_views_content", "content_id"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    ip_address = Column(String(45))
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")

    user = relationship("User", back_populates="views")
    content = relationship("Content", back_populates="views")


class Save(db.Model):
    """Bookmark/save to a named collection."""
    __tablename__ = "saves"
    __table_args__ = (
        UniqueConstraint("user_id", "content_id", "collection_name", name="uq_user_save_collection"),
        Index("ix_saves_content", "content_id"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    collection_name = Column(String(100), default="General")
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")

    user = relationship("User", back_populates="saves")
    content = relationship("Content", back_populates="saves")


class Reaction(db.Model):
    """Like or dislike on content or comment."""
    __tablename__ = "reactions"
    __table_args__ = (
        CheckConstraint("target_type IN ('content', 'comment')", name="ck_reaction_target_type"),
        UniqueConstraint("user_id", "target_type", "target_id", name="unique_user_reaction"),
        Index("ix_reactions_target", "target_type", "target_id"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # target_type: 'content' | 'comment'
    target_type = Column(String(20), nullable=False)
    target_id = Column(Integer, nullable=False)
    type = Column(String(20), nullable=False)   # 'like' | 'dislike'
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")

    user = relationship("User", back_populates="reactions")

    @property
    def content(self):
        if self.target_type == "content":
            from app.models.content import Content
            return db.session.get(Content, self.target_id)
        return None


class Comment(db.Model):
    """Threaded user comment on a content item."""
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_content", "content_id"),
        Index("ix_comments_parent", "parent_id"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"))
    content = Column(Text, nullable=False, default="")
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")
    sentiment = Column(String(20))
    confidence = Column(Float)
    like_count = Column(Integer, default=0, nullable=False)
    dislike_count = Column(Integer, default=0, nullable=False)
    share_count = Column(Integer, default=0, nullable=False)
    replies_count = Column(Integer, default=0, nullable=False)

    user = relationship("User", back_populates="comments")
    content_ref = relationship("Content", back_populates="comments",
                               foreign_keys=[content_id])
    parent = relationship("Comment", remote_side="Comment.id", back_populates="replies")
    replies = relationship("Comment", back_populates="parent")


class Share(db.Model):
    """Social share of content by a registered user."""
    __tablename__ = "shares"
    __table_args__ = (
        Index("ix_shares_content", "content_id"),
        Index("ix_shares_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(50))    # 'twitter', 'facebook', 'linkedin', 'copy'
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")

    user = relationship("User", back_populates="shares")
    content = relationship("Content", back_populates="shares")
