"""Newsletter and subscriber management service."""

from __future__ import annotations
import logging
import secrets
from typing import Any

from app.repositories.user_repo import UserRepository

log = logging.getLogger(__name__)


def subscribe_newsletter(email: str, user_id: int | None = None) -> dict[str, Any]:
    """Create or reactivate a newsletter subscription with a confirmation token."""
    email = email.strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return {"success": False, "message": "Please enter a valid email address."}

    token = secrets.token_urlsafe(32)

    sub, created = UserRepository.upsert_subscriber(email, user_id=user_id, confirmation_token=token)

    if sub.is_confirmed and not sub.unsubscribed_at:
        return {"success": True, "message": "You're already subscribed! Check your inbox."}

    log.info("Newsletter subscription token for %s: %s", email, token)

    return {"success": True, "message": "Thank you! Please check your inbox to confirm your subscription."}


__all__ = ["subscribe_newsletter"]
