"""Interactions blueprint for reactions, saves, shares, comments, and subscriptions."""

from __future__ import annotations
import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from pydantic import ValidationError

from app.extensions import limiter
from app.caching import invalidate_home_for_you
from app.services.interaction_service import toggle_reaction, toggle_save, record_share, submit_comment
from app.services.newsletter_service import (
    subscribe_newsletter,
    unsubscribe_current_user,
    unsubscribe_by_email,
)
from app.schemas import (
    InteractionPayload,
    CommentPayload,
    NewsletterSubscribePayload,
    NewsletterUnsubscribePayload,
)

log = logging.getLogger(__name__)

interactions_bp = Blueprint("interactions", __name__)


@interactions_bp.route("/handle-interaction", methods=["POST"])
@limiter.limit("30 per minute")
def handle_interaction():
    """Handle like, dislike, save, share, and impression interaction events with Pydantic validation."""
    raw_data = (request.get_json(silent=True) if request.is_json else None) or request.form.to_dict()

    try:
        payload = InteractionPayload.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"success": False, "message": "Invalid request.", "errors": err.errors()}), 400

    if payload.action == "impression":
        return jsonify({"success": True}), 200

    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Login required."}), 401

    if payload.action in ("like", "dislike"):
        result = toggle_reaction(current_user.id, payload.target_id, payload.action, target_type=payload.target_type)
    elif payload.action == "save":
        result = toggle_save(current_user.id, payload.target_id, payload.collection)
        if result.get("success"):
            invalidate_home_for_you(current_user.id)
    elif payload.action == "share":
        result = record_share(current_user.id, payload.target_id, payload.channel)
    else:
        result = {"success": False, "message": "Unknown action."}

    status = 200 if result.get("success") else 400
    return jsonify(result), status


@interactions_bp.route("/comments/submit", methods=["POST"])
@limiter.limit("30 per minute")
def submit_comment_route():
    """Submit a user comment with optional parent reply link and Pydantic validation."""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Please log in to post a comment."}), 401

    raw_data = (request.get_json(silent=True) if request.is_json else None) or request.form.to_dict()

    try:
        payload = CommentPayload.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"success": False, "message": "Invalid comment submission.", "errors": err.errors()}), 400

    result = submit_comment(user_id=current_user.id, content_id=payload.content_id, text=payload.text, parent_id=payload.parent_id)

    status = 200 if result.get("success") else 400
    return jsonify(result), status


@interactions_bp.route("/subscribe", methods=["POST"])
@limiter.limit("5 per minute")
def subscribe():
    """Register a new newsletter subscriber with double opt-in and Pydantic validation."""
    raw_data = (request.get_json(silent=True) if request.is_json else None) or request.form.to_dict()

    if current_user.is_authenticated and not raw_data.get("email"):
        raw_data["email"] = current_user.email

    try:
        payload = NewsletterSubscribePayload.model_validate(raw_data)
    except ValidationError:
        return jsonify({"success": False, "message": "Invalid email address."}), 400

    user_id = current_user.id if current_user.is_authenticated else None

    result = subscribe_newsletter(payload.email, user_id=user_id)
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@interactions_bp.route("/unsubscribe", methods=["POST"])
@limiter.limit("10 per minute")
def unsubscribe():
    """Unsubscribe authenticated user or guest by email."""
    if current_user.is_authenticated:
        result = unsubscribe_current_user(current_user.id)
        status = 200 if result.get("success") else 400
        return jsonify(result), status

    raw_data = (request.get_json(silent=True) if request.is_json else None) or request.form.to_dict()
    try:
        payload = NewsletterUnsubscribePayload.model_validate(raw_data)
    except ValidationError:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    if not payload.email or not payload.email.strip():
        return jsonify({"success": False, "message": "Email is required to unsubscribe."}), 400

    result = unsubscribe_by_email(payload.email)
    status = 200 if result.get("success") else 400
    return jsonify(result), status

