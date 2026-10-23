"""Admin syndication controller for social post scheduling and draft generation."""

from __future__ import annotations
import logging

from flask import Blueprint, jsonify, render_template, request

from app.repositories.content_repo import ContentRepository
from app.services.syndication_service import SyndicationService
from app.routes.admin import admin_required

log = logging.getLogger(__name__)

syndication_bp = Blueprint("syndication", __name__)


@syndication_bp.route("/")
@admin_required
def index():
    """Render syndication hub with reach statistics and recent articles."""
    hub_data = SyndicationService.get_syndication_hub_data()
    return render_template(
        "admin/syndication.html",
        stats=hub_data["stats"],
        recent_published=hub_data["recent_published"],
        platforms=hub_data["platforms"],
        active_tab="syndication",
    )


@syndication_bp.route("/generate/<int:content_id>", methods=["GET", "POST"])
@admin_required
def generate_drafts(content_id: int):
    """Generate platform-specific social media drafts for a content item."""
    drafts = SyndicationService.generate_drafts_for_article(content_id)
    if not drafts:
        return jsonify({"success": False, "message": "Content not found or invalid."}), 404

    if request.is_json or request.method == "POST":
        return jsonify({"success": True, "drafts": drafts})

    content = ContentRepository.get_by_id(content_id)
    return render_template("admin/syndication_drafts.html", content=content, drafts=drafts, active_tab="syndication")
