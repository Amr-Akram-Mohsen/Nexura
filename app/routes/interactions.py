"""Interactions blueprint for reactions, saves, shares, comments, and subscriptions."""

from __future__ import annotations
import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import limiter
from app.services.interaction_service import toggle_reaction, toggle_save, record_share, submit_comment
from app.services.newsletter_service import subscribe_newsletter

log = logging.getLogger(__name__)

interactions_bp = Blueprint("interactions", __name__)

VALID_ACTIONS = {"like", "dislike", "save", "share", "impression"}


@interactions_bp.route("/handle-interaction", methods=["POST"])
@limiter.limit("30 per minute")
def handle_interaction():
    """Handle like, dislike, save, share, and impression interaction events."""
    action = (request.form.get("action") or (request.json.get("action", "") if request.is_json else "")).strip()

    if action not in VALID_ACTIONS:
        return jsonify({"success": False, "message": "Invalid action."}), 400

    if action == "impression":
        return jsonify({"success": True}), 200

    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Login required."}), 401

    target_type = (request.form.get("target_type") or (request.json.get("target_type", "content") if request.is_json else "content") or "content").strip()

    target_id_raw = (
        request.form.get("target_id")
        or request.form.get("content_id")
        or (request.json.get("target_id") or request.json.get("content_id") if request.is_json else None)
    )

    try:
        target_id = int(target_id_raw)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid target ID."}), 400

    if action in ("like", "dislike"):
        result = toggle_reaction(current_user.id, target_id, action, target_type=target_type)
    elif action == "save":
        collection = request.form.get("collection", "General")
        result = toggle_save(current_user.id, target_id, collection)
    elif action == "share":
        channel = request.form.get("channel", "copy")
        result = record_share(current_user.id, target_id, channel)
    else:
        result = {"success": False, "message": "Unknown action."}

    status = 200 if result.get("success") else 400
    return jsonify(result), status


@interactions_bp.route("/comments/submit", methods=["POST"])
@limiter.limit("30 per minute")
def submit_comment_route():
    """Submit a user comment with optional parent reply link."""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Please log in to post a comment."}), 401

    content_id_raw = request.form.get("content_id") or (request.json.get("content_id") if request.is_json else None)
    text = request.form.get("text", "") or (request.json.get("text", "") if request.is_json else "")
    parent_id_raw = request.form.get("parent_id") or (request.json.get("parent_id") if request.is_json else None)

    try:
        content_id = int(content_id_raw)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid content ID."}), 400

    parent_id: int | None = None
    if parent_id_raw:
        try:
            parent_id = int(parent_id_raw)
        except (TypeError, ValueError):
            pass

    result = submit_comment(user_id=current_user.id, content_id=content_id, text=text, parent_id=parent_id)

    status = 200 if result.get("success") else 400
    return jsonify(result), status


@interactions_bp.route("/subscribe", methods=["POST"])
@limiter.limit("5 per minute")
def subscribe():
    """Register a new newsletter subscriber with double opt-in."""
    email = request.form.get("email", "").strip()
    user_id = current_user.id if current_user.is_authenticated else None

    result = subscribe_newsletter(email, user_id=user_id)
    status = 200 if result.get("success") else 400
    return jsonify(result), status
