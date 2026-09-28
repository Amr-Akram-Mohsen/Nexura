"""Admin syndication controller for social post scheduling and draft generation."""

from __future__ import annotations
import logging
from typing import Any

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import desc

from app.extensions import db
from app.models.content import Content
from app.models.distribution import DistributionPlatform, DistributionPost
from app.services.syndication_service import SyndicationService
from app.routes.admin import admin_required

log = logging.getLogger(__name__)

syndication_bp = Blueprint("syndication", __name__)


@syndication_bp.route("/")
@admin_required
def index():
    """Render syndication hub with reach statistics and recent articles."""
    stats = SyndicationService.get_syndication_stats()
    recent_published = (
        db.session.query(Content).filter(Content.is_published.is_(True), Content.object_type == "article").order_by(desc(Content.published_at)).limit(20).all()
    )

    platforms = db.session.query(DistributionPlatform).all()

    return render_template("admin/syndication.html", stats=stats, recent_published=recent_published, platforms=platforms, active_tab="syndication")


@syndication_bp.route("/generate/<int:content_id>", methods=["GET", "POST"])
@admin_required
def generate_drafts(content_id: int):
    """Generate platform-specific social media drafts for a content item."""
    drafts = SyndicationService.generate_drafts_for_article(content_id)
    if not drafts:
        return jsonify({"success": False, "message": "Content not found or invalid."}), 404

    if request.is_json or request.method == "POST":
        return jsonify({"success": True, "drafts": drafts})

    content = db.session.get(Content, content_id)
    return render_template("admin/syndication_drafts.html", content=content, drafts=drafts, active_tab="syndication")
