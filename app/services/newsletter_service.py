"""Newsletter and subscriber management service."""

from __future__ import annotations
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.email_service import EmailService

log = logging.getLogger(__name__)


def subscribe_newsletter(email: str, user_id: int | None = None) -> dict[str, Any]:
    """Create or reactivate a newsletter subscription with double opt-in or instant auth confirmation."""
    email = email.strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return {"success": False, "message": "Please enter a valid email address."}

    # If authenticated, check if this user already has an active subscription
    if user_id:
        user = db.session.get(User, user_id)
        if user and user.is_subscribed_to_newsletter:
            sub = user.newsletter_subscriber
            if sub.email == email:
                return {
                    "success": True,
                    "already_subscribed": True,
                    "is_confirmed": True,
                    "email": email,
                    "message": "You are already subscribed to the Nexura Weekly digest with this email.",
                }
            return {
                "success": False,
                "message": f"Your account is already subscribed as {sub.email}. Unsubscribe first to change emails.",
            }

    # Check if the email is already subscribed by someone else or guest
    sub_existing = UserRepository.get_subscriber_by_email(email)
    if sub_existing and sub_existing.is_confirmed and not sub_existing.unsubscribed_at:
        # If logged-in user owns this email, attach user_id if not attached
        if user_id and not sub_existing.user_id:
            sub_existing.user_id = user_id
            db.session.commit()
        return {
            "success": True,
            "already_subscribed": True,
            "is_confirmed": True,
            "email": email,
            "message": "You are already subscribed to the Nexura Weekly digest with this email.",
        }

    # Create or reactivate
    confirmation_token = secrets.token_urlsafe(32)
    unsubscribe_token = secrets.token_urlsafe(32)
    auto_confirm = bool(user_id)

    sub, created = UserRepository.upsert_subscriber(
        email,
        user_id=user_id,
        confirmation_token=None if auto_confirm else confirmation_token,
        unsubscribe_token=unsubscribe_token,
    )

    if auto_confirm:
        sub.is_confirmed = True
        sub.confirmation_token = None
        sub.unsubscribed_at = None
        db.session.commit()
        log.info("Newsletter subscription auto-confirmed for user_id=%s (%s)", user_id, email)
        return {
            "success": True,
            "already_subscribed": False,
            "is_confirmed": True,
            "email": email,
            "message": "You're now subscribed to Nexura Weekly! Digests will arrive in your inbox.",
        }

    # Guest flow: dispatch verification link
    try:
        EmailService.send_newsletter_confirmation(email, confirmation_token)
    except Exception as exc:
        log.warning("Could not dispatch newsletter confirmation email: %s", exc)

    return {
        "success": True,
        "already_subscribed": False,
        "is_confirmed": False,
        "email": email,
        "message": "Thank you! Please check your inbox to confirm your subscription.",
    }


def confirm_subscription(token: str) -> dict[str, Any]:
    """Confirm subscriber status via double opt-in token."""
    if not token or not token.strip():
        return {"success": False, "message": "Invalid or expired confirmation link."}

    sub = UserRepository.get_subscriber_by_confirmation_token(token.strip())
    if not sub:
        return {"success": False, "message": "Invalid or expired confirmation link."}

    sub.is_confirmed = True
    sub.confirmation_token = None
    sub.unsubscribed_at = None
    db.session.commit()

    log.info("Newsletter subscription confirmed for %s", sub.email)
    return {"success": True, "message": "Your subscription has been confirmed! Welcome to Nexura Weekly."}


def unsubscribe_newsletter(token: str) -> dict[str, Any]:
    """Deactivate subscription via unique unsubscribe token."""
    if not token or not token.strip():
        return {"success": False, "message": "Invalid or expired unsubscribe link."}

    sub = UserRepository.get_subscriber_by_unsubscribe_token(token.strip())
    if not sub:
        return {"success": False, "message": "Invalid or expired unsubscribe link."}

    sub.is_confirmed = False
    sub.unsubscribed_at = datetime.now(timezone.utc)
    db.session.commit()

    log.info("Newsletter subscriber %s unsubscribed via token", sub.email)
    return {"success": True, "message": "You have been successfully unsubscribed from Nexura Weekly."}


def unsubscribe_current_user(user_id: int) -> dict[str, Any]:
    """Unsubscribe the active authenticated user."""
    user = db.session.get(User, user_id)
    if not user or not user.newsletter_subscriber:
        return {"success": False, "message": "No active newsletter subscription found for this account."}
    sub = user.newsletter_subscriber
    sub.is_confirmed = False
    sub.unsubscribed_at = datetime.now(timezone.utc)
    db.session.commit()
    log.info("User %s (%s) unsubscribed from newsletter", user.id, sub.email)
    return {"success": True, "message": "You have been successfully unsubscribed from Nexura Weekly."}


def unsubscribe_by_email(email: str) -> dict[str, Any]:
    """Deactivate subscription by email address."""
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email or "." not in clean_email.split("@")[-1]:
        return {"success": False, "message": "Please enter a valid email address."}
    sub = UserRepository.get_subscriber_by_email(clean_email)
    if not sub or not sub.is_confirmed or sub.unsubscribed_at:
        return {"success": False, "message": "No active subscription found for this email."}
    sub.is_confirmed = False
    sub.unsubscribed_at = datetime.now(timezone.utc)
    db.session.commit()
    log.info("Subscriber %s unsubscribed by email", clean_email)
    return {"success": True, "message": "You have been successfully unsubscribed from Nexura Weekly."}


def generate_weekly_digest(user_id: int | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Compile top articles and video recommendations for the weekly email digest."""
    from app.services.recommendation_service import RecommendationService, trending_reason
    from app.serializers.content_serializers import serialize_content_card

    if user_id:
        feed = RecommendationService.get_personalized_feed_with_reasons(user_id, limit=limit)
        entries = feed.entries
    else:
        items = RecommendationService.get_trending_items(limit=limit)
        entries = [(item, trending_reason(item)) for item in items]

    digest_items: list[dict[str, Any]] = []
    for content, reason in entries:
        card = serialize_content_card(content)
        if reason:
            card["recommendation_reason"] = reason
        digest_items.append(card)

    return digest_items


__all__ = [
    "subscribe_newsletter",
    "confirm_subscription",
    "unsubscribe_newsletter",
    "unsubscribe_current_user",
    "unsubscribe_by_email",
    "generate_weekly_digest",
]



