"""
Nexura Phase 7 — Interactions Blueprint (§12, §19, §26)
Handles: /handle-interaction, /comments/submit, /subscribe
Rate limits: 30/min on interactions, 5/min on subscribe (§26)
CSRF enforced via flask-wtf on all POST routes.
"""
from __future__ import annotations
import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import limiter
from app.services.interaction_service import (
    toggle_reaction,
    toggle_save,
    record_share,
    submit_comment,
    subscribe_newsletter,
)

log = logging.getLogger(__name__)

interactions_bp = Blueprint("interactions", __name__)

VALID_ACTIONS = {"like", "dislike", "save", "share", "impression"}


# ─── Handle Interaction (§12 — like, dislike, save, share, impression) ────────
@interactions_bp.route("/handle-interaction", methods=["POST"])
@limiter.limit("30 per minute")
def handle_interaction():
    """
    Handles user reactions on content.
    Requires authentication for like/dislike/save/share.
    Impression events are accepted from IntersectionObserver (anonymous ok).
    """
    action = (request.form.get("action") or request.json.get("action", "") if request.is_json else request.form.get("action", "")).strip()
    content_id_raw = (request.form.get("content_id") or request.json.get("content_id") if request.is_json else request.form.get("content_id"))

    if action not in VALID_ACTIONS:
        return jsonify({"success": False, "message": "Invalid action."}), 400

    # Impression events can be anonymous (sent via sendBeacon)
    if action == "impression":
        # Lightweight — just return success; actual view recording happens via route
        return jsonify({"success": True}), 200

    # All other actions require login
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Login required."}), 401

    try:
        content_id = int(content_id_raw)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid content ID."}), 400

    if action in ("like", "dislike"):
        result = toggle_reaction(current_user.id, content_id, action)
    elif action == "save":
        collection = request.form.get("collection", "General")
        result = toggle_save(current_user.id, content_id, collection)
    elif action == "share":
        channel = request.form.get("channel", "copy")
        result = record_share(current_user.id, content_id, channel)
    else:
        result = {"success": False, "message": "Unknown action."}

    status = 200 if result.get("success") else 400
    return jsonify(result), status


# ─── Comment Submission (§12, §19) ───────────────────────────────────────────
@interactions_bp.route("/comments/submit", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def submit_comment_route():
    """Submit a threaded comment with optional parent_id."""
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

    result = submit_comment(
        user_id=current_user.id,
        content_id=content_id,
        text=text,
        parent_id=parent_id,
    )

    status = 200 if result.get("success") else 400
    return jsonify(result), status


# ─── Newsletter Subscribe (§12 — 5/min rate limit) ────────────────────────────
@interactions_bp.route("/subscribe", methods=["POST"])
@limiter.limit("5 per minute")
def subscribe():
    """Newsletter sign-up — creates double opt-in record."""
    email = request.form.get("email", "").strip()
    user_id = current_user.id if current_user.is_authenticated else None

    result = subscribe_newsletter(email, user_id=user_id)
    status = 200 if result.get("success") else 400
    return jsonify(result), status
