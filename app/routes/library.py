"""Library blueprint for reading history and saved bookmark collections."""

from __future__ import annotations
import logging
import math

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from app.repositories.user_repo import UserRepository
from app.serializers.content_serializers import serialize_content_card

log = logging.getLogger(__name__)

library_bp = Blueprint("library", __name__)

PER_PAGE = 24


@library_bp.route("/library")
@login_required
def index():
    """Render user library with history or saved collections tab."""
    tab = request.args.get("tab", "history")
    page = request.args.get("page", 1, type=int)

    history_count, saved_count = UserRepository.get_counts(current_user.id)

    if tab == "saved":
        collection = request.args.get("collection")
        items_raw, total = UserRepository.get_user_saves(current_user.id, collection_name=collection, page=page, per_page=PER_PAGE)
    else:
        tab = "history"
        items_raw, total = UserRepository.get_user_history(current_user.id, page=page, per_page=PER_PAGE)

    items = [serialize_content_card(c) for c in items_raw]
    total_pages = max(1, math.ceil(total / PER_PAGE))

    return render_template(
        "public/library.html", items=items, tab=tab, total=total, history_count=history_count, saved_count=saved_count, page=page, total_pages=total_pages
    )


@library_bp.route("/library/history/clear", methods=["POST"])
@login_required
def clear_history():
    """Clear all reading history for the current user."""
    UserRepository.clear_user_history(current_user.id)
    flash("Reading history cleared.", "info")
    return redirect(url_for("library.index", tab="history"))


@library_bp.route("/library/history/remove/<int:content_id>", methods=["POST"])
@login_required
def remove_history_item(content_id: int):
    """Remove a single item from user's reading history."""
    UserRepository.remove_from_user_history(current_user.id, content_id)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"success": True})
    flash("Item removed from history.", "info")
    return redirect(url_for("library.index", tab="history"))
