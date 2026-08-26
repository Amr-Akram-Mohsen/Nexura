"""
Nexura Phase 7 â€” User, NewsletterSubscriber, ContactMessage
"""
from __future__ import annotations

from flask_login import UserMixin
from sqlalchemy import (
    Boolean, CheckConstraint, Column, Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    """Registered platform user."""
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(google_id IS NULL AND provider IS NULL) OR (google_id IS NOT NULL AND provider IS NOT NULL)",
            name="ck_google_user",
        ),
        Index("ix_users_email", "email"),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(150), nullable=False, unique=True)
    name = Column(String(120))
    password_hash = Column(Text, nullable=False)
    google_id = Column(Text, unique=True)
    provider = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(TIMESTAMP(timezone=True))
    verification_sent_at = Column(TIMESTAMP(timezone=True))
    last_login_at = Column(TIMESTAMP(timezone=True))
    password_changed_at = Column(TIMESTAMP(timezone=True))
    password_reset_token = Column(String(255))
    password_reset_sent_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    views = relationship("View", back_populates="user", cascade="all, delete-orphan")
    saves = relationship("Save", back_populates="user", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    shares = relationship("Share", back_populates="user", cascade="all, delete-orphan")
    user_interests = relationship("UserInterest", back_populates="user", cascade="all, delete-orphan")
    newsletter_subscriber = relationship("NewsletterSubscriber", back_populates="user", uselist=False)

    def __repr__(self) -> str:
        return f"<User {self.email!r}>"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"
    __table_args__ = (
        Index("ix_newsletter_subscribers_email", "email"),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(150), nullable=False, unique=True)
    user_id = Column(Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    is_confirmed = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")
    unsubscribed_at = Column(TIMESTAMP(timezone=True))
    confirmation_token = Column(String(255))
    unsubscribe_token = Column(String(255))

    user = relationship("User", back_populates="newsletter_subscriber")

    def __repr__(self) -> str:
        return f"<NewsletterSubscriber {self.email!r}>"


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    __table_args__ = (
        Index("ix_contact_messages_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(120), nullable=False)
    subject = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(255))
    created_at = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")

    def __repr__(self) -> str:
        return f"<ContactMessage {self.email!r}>"
