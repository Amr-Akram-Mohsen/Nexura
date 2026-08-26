"""
Nexura Phase 7 — Library Blueprint (§12, §15)
Handles: /library?tab=history|saved
Reading history and organized save collections for authenticated users.
"""
from __future__ import annotations
import logging
import math

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.repositories.user_repo import UserRepository
from app.serializers.content_serializers import serialize_content_card

log = logging.getLogger(__name__)

library_bp = Blueprint("library", __name__)

PER_PAGE = 24


@library_bp.route("/library")
@login_required
def index():
    """User library — reading history and saved collections (§15)."""
    tab = request.args.get("tab", "history")
    page = request.args.get("page", 1, type=int)

    if tab == "saved":
        collection = request.args.get("collection")
        items_raw, total = UserRepository.get_user_saves(
            current_user.id,
            collection_name=collection,
            page=page,
            per_page=PER_PAGE,
        )
    else:
        tab = "history"  # Normalize
        items_raw, total = UserRepository.get_user_history(
            current_user.id,
            page=page,
            per_page=PER_PAGE,
        )

    items = [serialize_content_card(c) for c in items_raw]
    total_pages = max(1, math.ceil(total / PER_PAGE))

    return render_template(
        "public/library.html",
        items=items,
        tab=tab,
        total=total,
        page=page,
        total_pages=total_pages,
    )
