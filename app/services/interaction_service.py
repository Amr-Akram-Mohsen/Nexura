"""Interaction service handling reactions, saves, shares, comments, and views."""

from __future__ import annotations
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.interaction import Reaction, Save, Share, Comment, View
from app.models.content import Content
from app.models.user import NewsletterSubscriber
from app.repositories.user_repo import UserRepository
from app.utils.sanitizer import sanitize_text as clean_text

log = logging.getLogger(__name__)


def toggle_reaction(user_id: int, target_id: int, reaction_type: str, target_type: str = "content") -> dict[str, Any]:
    """Toggle like or dislike on content or comment, swapping or removing existing reactions."""
    if reaction_type not in ("like", "dislike"):
        return {"success": False, "message": "Invalid reaction type."}
    if target_type not in ("content", "comment"):
        return {"success": False, "message": "Invalid target type."}

    content_id = None
    target_obj = None

    if target_type == "content":
        content = db.session.get(Content, target_id)
        if not content:
            return {"success": False, "message": "Content not found."}
        content_id = content.id
        target_obj = content
    elif target_type == "comment":
        comment = db.session.get(Comment, target_id)
        if not comment:
            return {"success": False, "message": "Comment not found."}
        if comment.user_id == user_id:
            return {"success": False, "message": "You cannot react to your own comment."}
        content_id = comment.content_id
        target_obj = comment

    with db.session.begin_nested():
        existing = db.session.query(Reaction).filter(Reaction.user_id == user_id, Reaction.target_type == target_type, Reaction.target_id == target_id).first()

        user_reaction = None
        if existing:
            if existing.type == reaction_type:
                db.session.delete(existing)
                user_reaction = None
            else:
                existing.type = reaction_type
                existing.created_at = datetime.now(timezone.utc)
                user_reaction = reaction_type
        else:
            new_reaction = Reaction(user_id=user_id, target_type=target_type, target_id=target_id, type=reaction_type, created_at=datetime.now(timezone.utc))
            db.session.add(new_reaction)
            user_reaction = reaction_type

        db.session.flush()

        likes = (
            db.session.query(func.count(Reaction.id))
            .filter(Reaction.target_type == target_type, Reaction.target_id == target_id, Reaction.type == "like")
            .scalar()
            or 0
        )
        dislikes = (
            db.session.query(func.count(Reaction.id))
            .filter(Reaction.target_type == target_type, Reaction.target_id == target_id, Reaction.type == "dislike")
            .scalar()
            or 0
        )

        target_obj.like_count = likes
        target_obj.dislike_count = dislikes

    db.session.commit()

    try:
        from app.extensions import cache

        if content_id:
            cache.delete(f"content_page_{content_id}")
        if target_type == "content":
            cache.delete("home_page_data")
    except Exception as e:
        log.debug("Cache clear error: %s", e)

    return {
        "success": True,
        "toggled": user_reaction is not None,
        "user_reaction": user_reaction,
        "liked": user_reaction == "like",
        "disliked": user_reaction == "dislike",
        "like_count": likes,
        "dislike_count": dislikes,
        "count": likes if reaction_type == "like" else dislikes,
        "reaction_type": reaction_type,
        "target_type": target_type,
        "target_id": target_id,
    }


def toggle_save(user_id: int, content_id: int, collection_name: str = "General") -> dict[str, Any]:
    """Toggle saving content to a named user collection."""
    content = db.session.get(Content, content_id)
    if not content:
        return {"success": False, "message": "Content not found."}

    existing_save = db.session.query(Save).filter(Save.user_id == user_id, Save.content_id == content_id, Save.collection_name == collection_name).first()

    if existing_save:
        db.session.delete(existing_save)
        content.save_count = max(0, (content.save_count or 0) - 1)
        is_saved = False
        msg = "Removed from library."
    else:
        save = Save(user_id=user_id, content_id=content_id, collection_name=collection_name, created_at=datetime.now(timezone.utc))
        db.session.add(save)
        content.save_count = (content.save_count or 0) + 1
        is_saved = True
        msg = f"Saved to {collection_name}."

    db.session.commit()

    try:
        from app.extensions import cache

        cache.delete(f"content_page_{content_id}")
    except Exception as e:
        log.debug("Cache clear error: %s", e)

    return {"success": True, "saved": is_saved, "toggled": is_saved, "save_count": content.save_count, "message": msg}


def record_share(user_id: int, content_id: int, channel: str) -> dict[str, Any]:
    """Record a share event and increment content share counter."""
    content = db.session.get(Content, content_id)
    if not content:
        return {"success": False, "message": "Content not found."}

    share = Share(user_id=user_id, content_id=content_id, channel=channel[:50] if channel else "copy", created_at=datetime.now(timezone.utc))
    db.session.add(share)
    content.share_count = (content.share_count or 0) + 1
    db.session.commit()
    return {"success": True}


toggle_share = record_share


def record_view(content_id: int, *, user_id: int | None = None, ip_address: str | None = None) -> None:
    """Record a unique view per user or IP address."""
    if not user_id and not ip_address:
        return

    existing = None
    if user_id:
        existing = db.session.query(View.id).filter(View.user_id == user_id, View.content_id == content_id).first()
    elif ip_address:
        existing = db.session.query(View.id).filter(View.ip_address == ip_address, View.content_id == content_id, View.user_id.is_(None)).first()

    if existing:
        return

    try:
        view = View(user_id=user_id, content_id=content_id, ip_address=ip_address if not user_id else None, created_at=datetime.now(timezone.utc))
        db.session.add(view)
        content = db.session.get(Content, content_id)
        if content:
            content.view_count = (content.view_count or 0) + 1
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        log.debug("View already recorded.")


def submit_comment(user_id: int, content_id: int, text: str, parent_id: int | None = None) -> dict[str, Any]:
    """Submit a sanitized comment and schedule background sentiment scoring."""
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
        if parent.user_id == user_id:
            return {"success": False, "message": "You cannot reply to your own comment."}

    comment = Comment(user_id=user_id, content_id=content_id, parent_id=parent_id, content=clean, created_at=datetime.now(timezone.utc))
    db.session.add(comment)

    if parent_id:
        parent = db.session.get(Comment, parent_id)
        if parent:
            parent.replies_count = (parent.replies_count or 0) + 1

    content.comment_count = (content.comment_count or 0) + 1
    db.session.commit()

    try:
        from app.extensions import cache

        cache.delete(f"content_page_{content_id}")
    except Exception as e:
        log.debug("Cache clear error: %s", e)

    _score_comment_sentiment_async(comment.id)

    from app.models.user import User

    user = db.session.get(User, user_id)
    user_name = (user.name if user and user.name else (user.email.split("@")[0] if user and user.email else "Community Member")) if user else "Community Member"

    return {
        "success": True,
        "comment_id": comment.id,
        "comment": {
            "id": comment.id,
            "user_id": comment.user_id,
            "user_name": user_name,
            "content": comment.content,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "formatted_date": "Just now",
            "parent_id": comment.parent_id,
            "like_count": 0,
            "dislike_count": 0,
            "replies_count": 0,
            "replies": [],
        },
        "comment_count": content.comment_count,
        "message": "Comment posted.",
    }


def _score_comment_sentiment_async(comment_id: int) -> None:
    """Enqueue non-blocking sentiment analysis for a newly created comment."""
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


from app.services.newsletter_service import subscribe_newsletter
from app.utils.security import score_password

__all__ = ["toggle_reaction", "toggle_save", "toggle_share", "record_share", "submit_comment", "subscribe_newsletter", "score_password"]
