"""User repository for accounts, saved collections, history, and subscribers."""

from __future__ import annotations
import secrets
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

    @staticmethod
    def get_by_id(user_id: int) -> User | None:
        """Fetch user by ID."""
        return db.session.get(User, user_id)

    @staticmethod
    def get_by_email(email: str) -> User | None:
        """Fetch user by email address."""
        if not email:
            return None
        return db.session.query(User).filter(func.lower(User.email) == email.strip().lower()).first()

    @staticmethod
    def get_by_google_id(google_id: str) -> User | None:
        """Fetch user by Google OAuth ID."""
        if not google_id:
            return None
        return db.session.query(User).filter(User.google_id == google_id).first()

    @staticmethod
    def get_by_reset_token(token: str) -> User | None:
        """Fetch user by password reset token."""
        if not token:
            return None
        return db.session.query(User).filter(User.password_reset_token == token).first()

    @staticmethod
    def get_by_verification_token(token: str) -> User | None:
        """Fetch user by email verification token."""
        if not token:
            return None
        return db.session.query(User).filter(User.email_verification_token == token).first()

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
        """Verify user password hash."""
        if not user.password_hash:
            return False
        return check_password_hash(user.password_hash, password)

    @staticmethod
    def update_password(user: User, new_password: str) -> None:
        """Update user password hash and clear reset token."""
        user.password_hash = generate_password_hash(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        user.password_reset_token = None
        user.password_reset_sent_at = None
        db.session.commit()

    @staticmethod
    def register_unverified_user(
        *,
        email: str,
        name: str,
        password: str,
        verification_token: str,
    ) -> User:
        """Create and persist a new unverified user with verification token."""
        now_utc = datetime.now(timezone.utc)
        user = User(
            email=email.strip().lower(),
            name=name,
            password_hash=generate_password_hash(password),
            is_verified=False,
            is_active=True,
            is_admin=False,
            created_at=now_utc,
            verification_sent_at=now_utc,
            email_verification_token=verification_token,
            email_verification_sent_at=now_utc,
            password_reset_token=None,
        )
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def record_login(user: User) -> None:
        """Update last_login_at timestamp on successful login."""
        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()

    @staticmethod
    def verify_email(user: User) -> None:
        """Mark user's email as verified and clear verification token."""
        user.is_verified = True
        user.verified_at = datetime.now(timezone.utc)
        user.email_verification_token = None
        db.session.commit()

    @staticmethod
    def set_email_verification_token(user: User, token: str) -> None:
        """Update email verification token and timestamps."""
        now_utc = datetime.now(timezone.utc)
        user.email_verification_token = token
        user.email_verification_sent_at = now_utc
        user.verification_sent_at = now_utc
        db.session.commit()

    @staticmethod
    def set_password_reset_token(user: User, token: str) -> None:
        """Store password reset token and sent timestamp."""
        user.password_reset_token = token
        user.password_reset_sent_at = datetime.now(timezone.utc)
        db.session.commit()

    @staticmethod
    def find_or_create_google_user(
        *,
        email: str,
        google_id: str,
        name: str | None = None,
    ) -> tuple[User, bool]:
        """Find an existing user or create a new user from Google OAuth profile.

        Returns a tuple of (user, is_new_user).
        """
        clean_email = email.strip().lower()
        user = UserRepository.get_by_email(clean_email)
        now_utc = datetime.now(timezone.utc)

        if not user:
            user = User(
                email=clean_email,
                name=name or (clean_email.split("@")[0] if clean_email else "Google User"),
                password_hash=generate_password_hash(secrets.token_urlsafe(32)),
                google_id=google_id,
                provider="google",
                is_verified=True,
                verified_at=now_utc,
                is_active=True,
                is_admin=False,
                created_at=now_utc,
                last_login_at=now_utc,
            )
            db.session.add(user)
            db.session.commit()
            return user, True
        else:
            if not user.google_id:
                user.google_id = google_id
                user.provider = "google"
            user.is_verified = True
            user.last_login_at = now_utc
            db.session.commit()
            return user, False

    @staticmethod
    def update_profile(user: User, *, name: str | None = None) -> None:
        """Update user profile fields."""
        if name is not None:
            user.name = name.strip()
        db.session.commit()

    @staticmethod
    def get_user_saves(user_id: int, *, collection_name: str | None = None, page: int = 1, per_page: int = 24) -> tuple[list[Content], int]:
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
        contents = query.order_by(desc(Save.created_at)).offset(max(0, (page - 1) * per_page)).limit(per_page).all()
        resolved = ContentRepository.resolve_polymorphic_payloads(contents)
        return resolved, total

    @staticmethod
    def is_content_saved(user_id: int, content_id: int) -> bool:
        """Check if content item is saved by user."""
        return bool(db.session.query(Save.id).filter(Save.user_id == user_id, Save.content_id == content_id).first())

    @staticmethod
    def get_user_history(user_id: int, *, page: int = 1, per_page: int = 24) -> tuple[list[Content], int]:
        """Fetch user's reading history with polymorphic payloads resolved, deduplicated by latest view."""
        subquery = (
            db.session.query(
                View.content_id.label("content_id"),
                func.max(View.created_at).label("last_viewed_at"),
            )
            .filter(View.user_id == user_id)
            .group_by(View.content_id)
            .subquery()
        )
        total = db.session.query(func.count(subquery.c.content_id)).scalar() or 0
        contents = (
            db.session.query(Content)
            .join(subquery, subquery.c.content_id == Content.id)
            .options(
                joinedload(Content.section),
                joinedload(Content.category),
                joinedload(Content.source),
                selectinload(Content.content_entities).joinedload(ContentEntity.entity),
            )
            .order_by(desc(subquery.c.last_viewed_at))
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
        deleted = db.session.query(View).filter(View.user_id == user_id, View.content_id == content_id).delete()
        db.session.commit()
        return bool(deleted)

    @staticmethod
    def get_counts(user_id: int) -> tuple[int, int]:
        """Get (history_count, saved_count) for a user."""
        history_cnt = db.session.query(func.count(func.distinct(View.content_id))).filter(View.user_id == user_id).scalar() or 0
        saved_cnt = db.session.query(func.count(Save.id)).filter(Save.user_id == user_id).scalar() or 0
        return history_cnt, saved_cnt

    @staticmethod
    def get_subscriber_by_email(email: str) -> NewsletterSubscriber | None:
        """Fetch newsletter subscriber by email."""
        if not email:
            return None
        return db.session.query(NewsletterSubscriber).filter(func.lower(NewsletterSubscriber.email) == email.strip().lower()).first()

    @staticmethod
    def get_subscriber_by_confirmation_token(token: str) -> NewsletterSubscriber | None:
        """Fetch subscriber by confirmation token."""
        if not token:
            return None
        return db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.confirmation_token == token).first()

    @staticmethod
    def get_subscriber_by_unsubscribe_token(token: str) -> NewsletterSubscriber | None:
        """Fetch subscriber by unsubscribe token."""
        if not token:
            return None
        return db.session.query(NewsletterSubscriber).filter(NewsletterSubscriber.unsubscribe_token == token).first()

    @staticmethod
    def upsert_subscriber(
        email: str, *, user_id: int | None = None, confirmation_token: str | None = None, unsubscribe_token: str | None = None
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
                unsubscribe_token=unsubscribe_token,
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
            if unsubscribe_token and not sub.unsubscribe_token:
                sub.unsubscribe_token = unsubscribe_token
        if user_id:
            # Ensure no other subscriber record has this user_id
            db.session.query(NewsletterSubscriber).filter(
                NewsletterSubscriber.user_id == user_id,
                func.lower(NewsletterSubscriber.email) != clean_email,
            ).update({"user_id": None}, synchronize_session=False)
            sub.user_id = user_id

        db.session.commit()
        return sub, created

    @staticmethod
    def create_contact_message(
        *, name: str, email: str, subject: str, message: str, ip_address: str | None = None, user_agent: str | None = None
    ) -> ContactMessage:
        """Create and persist a contact message."""
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

    @staticmethod
    def get_subscribers(limit: int = 50) -> list[NewsletterSubscriber]:
        """Fetch latest newsletter subscribers."""
        return db.session.query(NewsletterSubscriber).order_by(desc(NewsletterSubscriber.created_at)).limit(limit).all()

    @staticmethod
    def get_subscriber_counts() -> tuple[int, int]:
        """Return (total_subscribers, confirmed_subscribers)."""
        total = db.session.query(func.count(NewsletterSubscriber.id)).scalar() or 0
        confirmed = db.session.query(func.count(NewsletterSubscriber.id)).filter(NewsletterSubscriber.is_confirmed.is_(True)).scalar() or 0
        return total, confirmed
