"""
Nexura Phase 7 — User Repository
Data access layer for User accounts, Saved collections, View history,
Newsletter subscribers, and Contact messages.
"""
from __future__ import annotations
from typing import Sequence
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models.user import User, NewsletterSubscriber, ContactMessage
from app.models.interaction import Save, View
from app.models.content import Content, ContentEntity
from app.repositories.content_repo import ContentRepository


class UserRepository:
    """Data access operations for user profiles, history, and library."""

    # ---------- Users ----------

    @staticmethod
    def get_by_id(user_id: int) -> User | None:
        return db.session.get(User, user_id)

    @staticmethod
    def get_by_email(email: str) -> User | None:
        if not email:
            return None
        return db.session.query(User).filter(func.lower(User.email) == email.strip().lower()).first()

    @staticmethod
    def get_by_google_id(google_id: str) -> User | None:
        if not google_id:
            return None
        return db.session.query(User).filter(User.google_id == google_id).first()

    @staticmethod
    def get_by_reset_token(token: str) -> User | None:
        if not token:
            return None
        return db.session.query(User).filter(User.password_reset_token == token).first()

    @staticmethod
    def create(
        *,
        email: str,
        password: str | None = None,
        name: str | None = None,
        google_id: str | None = None,
        provider: str | None = None,
        is_admin: bool = False,
        is_verified: bool = False,
    ) -> User:
        """Create and persist a new user."""
        password_hash = generate_password_hash(password) if password else ""
        user = User(
            email=email.strip().lower(),
            name=name,
            password_hash=password_hash,
            google_id=google_id,
            provider=provider,
            is_admin=is_admin,
            is_verified=is_verified,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def verify_password(user: User, password: str) -> bool:
        if not user.password_hash:
            return False
        return check_password_hash(user.password_hash, password)

    @staticmethod
    def update_password(user: User, new_password: str) -> None:
        user.password_hash = generate_password_hash(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        user.password_reset_token = None
        user.password_reset_sent_at = None
        db.session.commit()

    # ---------- User Library: Saves / Bookmarks ----------

    @staticmethod
    def get_user_saves(
        user_id: int,
        *,
        collection_name: str | None = None,
        page: int = 1,
        per_page: int = 24,
    ) -> tuple[list[Content], int]:
        """Fetch user's saved bookmarks with polymorphic payloads resolved."""
        query = (
            db.session.query(Content)
            .join(Save, Save.content_id == Content.id)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                selectinload(Content.content_entities).joinedload(ContentEntity.entity),
            )
            .filter(Save.user_id == user_id)
        )
        if collection_name:
            query = query.filter(Save.collection_name == collection_name)

        total = query.with_entities(func.count(Content.id)).scalar() or 0
        contents = (
            query.order_by(desc(Save.created_at))
            .offset(max(0, (page - 1) * per_page))
            .limit(per_page)
            .all()
        )
        resolved = ContentRepository.resolve_polymorphic_payloads(contents)
        return resolved, total

    @staticmethod
    def is_content_saved(user_id: int, content_id: int) -> bool:
        return bool(
            db.session.query(Save.id)
            .filter(Save.user_id == user_id, Save.content_id == content_id)
            .first()
        )

    # ---------- User Reading / View History ----------

    @staticmethod
    def get_user_history(
        user_id: int,
        *,
        page: int = 1,
        per_page: int = 24,
    ) -> tuple[list[Content], int]:
        """Fetch user's reading history."""
        query = (
            db.session.query(Content)
            .join(View, View.content_id == Content.id)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                selectinload(Content.content_entities).joinedload(ContentEntity.entity),
            )
            .filter(View.user_id == user_id)
        )
        total = query.with_entities(func.count(func.distinct(Content.id))).scalar() or 0
        contents = (
            query.order_by(desc(View.created_at))
            .offset(max(0, (page - 1) * per_page))
            .limit(per_page)
            .all()
        )
        resolved = ContentRepository.resolve_polymorphic_payloads(contents)
        return resolved, total

    @staticmethod
    def clear_user_history(user_id: int) -> int:
        """Clear all view history for a user."""
        count = db.session.query(View).filter(View.user_id == user_id).delete()
        db.session.commit()
        return count

    @staticmethod
    def remove_from_user_history(user_id: int, content_id: int) -> bool:
        """Remove a specific content item from user's view history."""
        deleted = (
            db.session.query(View)
            .filter(View.user_id == user_id, View.content_id == content_id)
            .delete()
        )
        db.session.commit()
        return bool(deleted)

    @staticmethod
    def get_counts(user_id: int) -> tuple[int, int]:
        """Get (history_count, saved_count) for a user."""
        history_cnt = (
            db.session.query(func.count(func.distinct(View.content_id)))
            .filter(View.user_id == user_id)
            .scalar() or 0
        )
        saved_cnt = (
            db.session.query(func.count(Save.id))
            .filter(Save.user_id == user_id)
            .scalar() or 0
        )
        return history_cnt, saved_cnt

    # ---------- Newsletter Subscribers ----------

    @staticmethod
    def get_subscriber_by_email(email: str) -> NewsletterSubscriber | None:
        if not email:
            return None
        return (
            db.session.query(NewsletterSubscriber)
            .filter(func.lower(NewsletterSubscriber.email) == email.strip().lower())
            .first()
        )

    @staticmethod
    def upsert_subscriber(
        email: str,
        *,
        user_id: int | None = None,
        confirmation_token: str | None = None,
    ) -> tuple[NewsletterSubscriber, bool]:
        """Subscribe or re-subscribe an email. Returns (subscriber, is_created)."""
        clean_email = email.strip().lower()
        sub = UserRepository.get_subscriber_by_email(clean_email)
        created = False
        if not sub:
            sub = NewsletterSubscriber(
                email=clean_email,
                user_id=user_id,
                confirmation_token=confirmation_token,
                is_confirmed=False,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(sub)
            created = True
        else:
            if sub.unsubscribed_at:
                sub.unsubscribed_at = None
            if confirmation_token:
                sub.confirmation_token = confirmation_token
            if user_id and not sub.user_id:
                sub.user_id = user_id

        db.session.commit()
        return sub, created

    # ---------- Contact Messages ----------

    @staticmethod
    def create_contact_message(
        *,
        name: str,
        email: str,
        subject: str,
        message: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ContactMessage:
        msg = ContactMessage(
            name=name,
            email=email.strip().lower(),
            subject=subject,
            message=message,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(msg)
        db.session.commit()
        return msg
