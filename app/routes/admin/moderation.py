"""
Nexura Phase 7 — Admin Moderation & Community Safety Controller (§18.6, §19)
Handles:
1. Threaded user comment moderation queue (Approve, Soft-delete, Hard-delete).
2. AI Sentiment & spam inspection.
3. Newsletter subscriber hygiene and confirmation tracking.
"""
from __future__ import annotations
import logging
from typing import Any

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.interaction import Comment
from app.models.content import Content
from app.models.user import NewsletterSubscriber
from app.routes.admin import admin_required

log = logging.getLogger(__name__)

moderation_bp = Blueprint("moderation", __name__)


@moderation_bp.route("/")
@admin_required
def index():
    """Community Moderation & Discussion Queue."""
    comments = (
        db.session.query(Comment)
        .options(joinedload(Comment.user), joinedload(Comment.content_ref))
        .order_by(desc(Comment.id))
        .limit(50)
        .all()
    )

    subscribers = (
        db.session.query(NewsletterSubscriber)
        .order_by(desc(NewsletterSubscriber.created_at))
        .limit(50)
        .all()
    )

    total_comments = db.session.query(func.count(Comment.id)).scalar() or 0
    total_subscribers = db.session.query(func.count(NewsletterSubscriber.id)).scalar() or 0
    confirmed_subscribers = (
        db.session.query(func.count(NewsletterSubscriber.id))
        .filter(NewsletterSubscriber.is_confirmed.is_(True))
        .scalar() or 0
    )

    return render_template(
        "admin/moderation.html",
        comments=comments,
        subscribers=subscribers,
        total_comments=total_comments,
        total_subscribers=total_subscribers,
        confirmed_subscribers=confirmed_subscribers,
        active_tab="moderation",
    )


@moderation_bp.route("/comments/<int:comment_id>/<action>", methods=["POST"])
@admin_required
def moderate_comment(comment_id: int, action: str):
    """
    Moderate user comment (Phase 7 §19):
    Actions: approve, soft_delete, hard_delete.
    """
    comment = db.session.get(Comment, comment_id)
    if not comment:
        return jsonify({"success": False, "message": "Comment not found."}), 404

    if action == "approve":
        comment.sentiment = "positive" if not comment.sentiment else comment.sentiment
        db.session.commit()
        return jsonify({"success": True, "message": "Comment approved."})

    elif action == "soft_delete":
        comment.content = "[This comment was removed by moderators for violating community guidelines.]"
        db.session.commit()
        return jsonify({"success": True, "message": "Comment soft-deleted."})

    elif action == "hard_delete":
        content_id = comment.content_id
        db.session.delete(comment)
        if content_id:
            content = db.session.get(Content, content_id)
            if content:
                content.comment_count = max(0, (content.comment_count or 0) - 1)
        db.session.commit()
        return jsonify({"success": True, "message": "Comment permanently deleted."})

    else:
        return jsonify({"success": False, "message": f"Invalid moderation action '{action}'."}), 400
