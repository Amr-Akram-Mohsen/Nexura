"""Admin moderation controller for comment moderation and subscriber tracking."""

from __future__ import annotations
import logging

from flask import Blueprint, jsonify, render_template

from app.repositories.analytics_repo import AnalyticsRepository
from app.repositories.user_repo import UserRepository
from app.services.interaction_service import InteractionService
from app.routes.admin import admin_required

log = logging.getLogger(__name__)

moderation_bp = Blueprint("moderation", __name__)


@moderation_bp.route("/")
@admin_required
def index():
    """Render community moderation and discussion queue with subscriber metrics."""
    comments = AnalyticsRepository.get_moderation_queue(limit=50)
    subscribers = UserRepository.get_subscribers(limit=50)
    total_comments = AnalyticsRepository.get_total_comments()
    total_subscribers, confirmed_subscribers = UserRepository.get_subscriber_counts()

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
    """Execute moderation action (approve, soft_delete, hard_delete) on a user comment."""
    success, message, status_code = InteractionService.moderate_comment(comment_id, action)
    return jsonify({"success": success, "message": message}), status_code
