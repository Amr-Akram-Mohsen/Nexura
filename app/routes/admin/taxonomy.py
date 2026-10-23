"""Admin taxonomy controller for taxonomy overview, duplicate entity detection, and merging."""

from __future__ import annotations
import logging

from flask import Blueprint, jsonify, render_template, request

from app.caching import invalidate_layout
from app.repositories.taxonomy_repo import TaxonomyRepository
from app.services.taxonomy_service import TaxonomyService
from app.routes.admin import admin_required

log = logging.getLogger(__name__)

taxonomy_bp = Blueprint("taxonomy", __name__)


@taxonomy_bp.route("/")
@admin_required
def index():
    """Render taxonomy overview with sections, categories, popular entities, and merge suggestions."""
    sections = TaxonomyRepository.get_sections(active_only=False)
    categories = TaxonomyRepository.get_all_categories()
    popular_entities = TaxonomyRepository.get_popular_entities(limit=30)
    sources = TaxonomyRepository.get_all_sources()
    merge_candidates = TaxonomyService.find_duplicate_entities(threshold=0.82, limit=15)

    return render_template(
        "admin/taxonomy.html",
        sections=sections,
        categories=categories,
        popular_entities=popular_entities,
        sources=sources,
        merge_candidates=merge_candidates,
        active_tab="taxonomy",
    )


@taxonomy_bp.route("/merge", methods=["POST"])
@admin_required
def merge_entities():
    """Re-point all content entities from source to target and remove source entity."""
    source_id = request.form.get("source_id", type=int)
    target_id = request.form.get("target_id", type=int)

    if not source_id or not target_id or source_id == target_id:
        return jsonify({"success": False, "message": "Invalid source or target entity ID."}), 400

    moved_count = TaxonomyRepository.merge_entities(source_id, target_id)
    invalidate_layout()

    return jsonify({"success": True, "moved_count": moved_count, "message": f"Successfully merged entities. Updated {moved_count} associations."})
