"""
Nexura Phase 7 — Interaction Service (§12, §14, §15, §19)
Handles: like/dislike toggle, save/unsave, share, comment submission,
newsletter subscribe, and view recording.
All mutating operations are atomic and cascaded.
"""
from __future__ import annotations
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.interaction import Reaction, Save, Share, Comment, View
from app.models.content import Content
from app.models.user import NewsletterSubscriber
from app.repositories.user_repo import UserRepository
from app.utils.sanitizer import sanitize_text as clean_text

log = logging.getLogger(__name__)

# ─── Reaction Toggle (like / dislike) ────────────────────────────────────────
def toggle_reaction(
    user_id: int, content_id: int, reaction_type: str
) -> dict[str, Any]:
    """
    Toggle a like or dislike on content. Implements atomic reaction mutation:
    - If same reaction exists → remove it (untoggle).
    - If opposite reaction exists → swap it.
    - If no reaction → create it.
    Returns: {toggled: bool, count: int, action: str}
    """
    if reaction_type not in ("like", "dislike"):
        return {"success": False, "message": "Invalid reaction type."}

    opposite = "dislike" if reaction_type == "like" else "like"

    with db.session.begin_nested():
        existing = (
            db.session.query(Reaction)
            .filter(
                Reaction.user_id == user_id,
                Reaction.target_type == "content",
                Reaction.target_id == content_id,
            )
            .first()
        )

        content = db.session.get(Content, content_id)
        if not content:
            return {"success": False, "message": "Content not found."}

        toggled = False

        if existing:
            if existing.type == reaction_type:
                # Same → untoggle
                db.session.delete(existing)
                if reaction_type == "like":
                    content.like_count = max(0, (content.like_count or 0) - 1)
                else:
                    content.dislike_count = max(0, (content.dislike_count or 0) - 1)
                toggled = False
            else:
                # Swap → remove opposite, add new
                if existing.type == "like":
                    content.like_count = max(0, (content.like_count or 0) - 1)
                else:
                    content.dislike_count = max(0, (content.dislike_count or 0) - 1)
                existing.type = reaction_type
                existing.created_at = datetime.now(timezone.utc)
                if reaction_type == "like":
                    content.like_count = (content.like_count or 0) + 1
                else:
                    content.dislike_count = (content.dislike_count or 0) + 1
                toggled = True
        else:
            # Create new reaction
            new_reaction = Reaction(
                user_id=user_id,
                target_type="content",
                target_id=content_id,
                type=reaction_type,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(new_reaction)
            if reaction_type == "like":
                content.like_count = (content.like_count or 0) + 1
            else:
                content.dislike_count = (content.dislike_count or 0) + 1
            toggled = True

    db.session.commit()

    count = content.like_count if reaction_type == "like" else content.dislike_count
    return {
        "success": True,
        "toggled": toggled,
        "count": count,
        "reaction_type": reaction_type,
    }


# ─── Save / Unsave ────────────────────────────────────────────────────────────
def toggle_save(
    user_id: int,
    content_id: int,
    collection_name: str = "General",
) -> dict[str, Any]:
    """
    Toggle a save on content for the given collection.
    Returns: {success, saved: bool, message}
    """
    content = db.session.get(Content, content_id)
    if not content:
        return {"success": False, "message": "Content not found."}

    existing_save = (
        db.session.query(Save)
        .filter(
            Save.user_id == user_id,
            Save.content_id == content_id,
            Save.collection_name == collection_name,
        )
        .first()
    )

    if existing_save:
        db.session.delete(existing_save)
        content.save_count = max(0, (content.save_count or 0) - 1)
        db.session.commit()
        return {"success": True, "saved": False, "message": "Removed from library."}
    else:
        save = Save(
            user_id=user_id,
            content_id=content_id,
            collection_name=collection_name,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(save)
        content.save_count = (content.save_count or 0) + 1
        db.session.commit()
        return {"success": True, "saved": True, "message": "Saved to library!"}


# ─── Record Share ─────────────────────────────────────────────────────────────
def record_share(user_id: int, content_id: int, channel: str) -> dict[str, Any]:
    """Record a content share event. De-duplication not enforced on shares."""
    content = db.session.get(Content, content_id)
    if not content:
        return {"success": False, "message": "Content not found."}

    share = Share(
        user_id=user_id,
        content_id=content_id,
        channel=channel[:50] if channel else "copy",
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(share)
    content.share_count = (content.share_count or 0) + 1
    db.session.commit()
    return {"success": True}


# ─── Record View ─────────────────────────────────────────────────────────────
def record_view(
    content_id: int,
    *,
    user_id: int | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Idempotent view recording using ON CONFLICT DO NOTHING semantics.
    Uses partial unique indexes: uq_views_auth and uq_views_anon.
    """
    if not user_id and not ip_address:
        return

    existing = None
    if user_id:
        existing = db.session.query(View.id).filter(
            View.user_id == user_id, View.content_id == content_id
        ).first()
    elif ip_address:
        existing = db.session.query(View.id).filter(
            View.ip_address == ip_address,
            View.content_id == content_id,
            View.user_id.is_(None),
        ).first()

    if existing:
        return

    try:
        view = View(
            user_id=user_id,
            content_id=content_id,
            ip_address=ip_address if not user_id else None,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(view)
        # Increment view counter atomically
        content = db.session.get(Content, content_id)
        if content:
            content.view_count = (content.view_count or 0) + 1
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        log.debug("View already recorded (race condition handled).")


# ─── Submit Comment (§19) ─────────────────────────────────────────────────────
def submit_comment(
    user_id: int,
    content_id: int,
    text: str,
    parent_id: int | None = None,
) -> dict[str, Any]:
    """
    Submit a user comment with sanitized text.
    Calls HuggingFace sentiment asynchronously (non-blocking).
    Returns: {success, comment_id, message}
    """
    if not text or not text.strip():
        return {"success": False, "message": "Comment cannot be empty."}

    clean = clean_text(text)
    if len(clean) < 2:
        return {"success": False, "message": "Comment too short."}
    if len(clean) > 2000:
        return {"success": False, "message": "Comment exceeds 2000 characters."}

    content = db.session.get(Content, content_id)
    if not content:
        return {"success": False, "message": "Content not found."}

    if parent_id:
        parent = db.session.get(Comment, parent_id)
        if not parent or parent.content_id != content_id:
            return {"success": False, "message": "Invalid parent comment."}

    comment = Comment(
        user_id=user_id,
        content_id=content_id,
        parent_id=parent_id,
        content=clean,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(comment)

    # Update parent reply count
    if parent_id:
        parent = db.session.get(Comment, parent_id)
        if parent:
            parent.replies_count = (parent.replies_count or 0) + 1

    # Update content comment count
    content.comment_count = (content.comment_count or 0) + 1
    db.session.commit()

    # Async sentiment scoring (non-blocking — fire and forget)
    _score_comment_sentiment_async(comment.id)

    return {
        "success": True,
        "comment_id": comment.id,
        "message": "Comment posted.",
    }


def _score_comment_sentiment_async(comment_id: int) -> None:
    """Enqueue sentiment scoring — best-effort, non-blocking."""
    try:
        from threading import Thread
        from app.ingestion.clients import HuggingFaceClient

        def _worker():
            from app import create_app
            app = create_app()
            with app.app_context():
                comment = db.session.get(Comment, comment_id)
                if not comment:
                    return
                try:
                    client = HuggingFaceClient()
                    result = client.analyze_sentiment(comment.content)
                    comment.sentiment = result.get("label", "neutral")
                    comment.confidence = result.get("score", 0.5)
                    db.session.commit()
                except Exception as exc:
                    log.debug("Sentiment scoring skipped for comment %s: %s", comment_id, exc)

        t = Thread(target=_worker, daemon=True)
        t.start()
    except Exception as exc:
        log.debug("Could not start sentiment thread: %s", exc)


# ─── Newsletter Subscribe (§12 — 5/min rate limit enforced in route) ─────────
def subscribe_newsletter(
    email: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    """
    Create or reactivate a newsletter subscription.
    Issues a confirmation token for double opt-in.
    Returns: {success, message}
    """
    email = email.strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return {"success": False, "message": "Please enter a valid email address."}

    token = secrets.token_urlsafe(32)

    sub, created = UserRepository.upsert_subscriber(
        email, user_id=user_id, confirmation_token=token
    )

    if sub.is_confirmed and not sub.unsubscribed_at:
        return {
            "success": True,
            "message": "You're already subscribed! Check your inbox.",
        }

    # In production, send confirmation email here via Flask-Mail
    log.info("Newsletter subscription token for %s: %s", email, token)

    return {
        "success": True,
        "message": "Thank you! Please check your inbox to confirm your subscription.",
    }


# ─── Password Strength Scorer (§14) ──────────────────────────────────────────
_LOWERCASE_RE = re.compile(r"[a-z]")
_UPPERCASE_RE = re.compile(r"[A-Z]")
_DIGIT_RE = re.compile(r"\d")
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


def score_password(password: str) -> dict[str, Any]:
    """
    Returns a score 0–4 for password diversity.
    Phase 7 §14: minimum 8 chars + character class diversity.
    """
    if len(password) < 8:
        return {"score": 0, "valid": False, "message": "Must be at least 8 characters."}

    score = 0
    if _LOWERCASE_RE.search(password):
        score += 1
    if _UPPERCASE_RE.search(password):
        score += 1
    if _DIGIT_RE.search(password):
        score += 1
    if _SPECIAL_RE.search(password):
        score += 1

    if score < 2:
        return {
            "score": score,
            "valid": False,
            "message": "Too weak — add uppercase letters, numbers, or symbols.",
        }

    return {
        "score": score,
        "valid": True,
        "message": ["", "Weak", "Fair", "Good", "Strong"][score],
    }
