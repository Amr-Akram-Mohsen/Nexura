"""Admin taxonomy controller for taxonomy overview, duplicate entity detection, and merging."""

from __future__ import annotations
import difflib
import logging
from typing import Any

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import func

from app.extensions import db
from app.caching import invalidate_layout
from app.models.taxonomy import Section, Category, Entity
from app.models.source import Source
from app.models.content import ContentEntity
from app.repositories.taxonomy_repo import TaxonomyRepository
from app.routes.admin import admin_required

log = logging.getLogger(__name__)

taxonomy_bp = Blueprint("taxonomy", __name__)


def find_duplicate_entities(threshold: float = 0.85, limit: int = 20) -> list[dict[str, Any]]:
    """Find entity pairs with high string similarity for editorial merge review."""
    entities = db.session.query(Entity.id, Entity.name, Entity.slug, Entity.entity_type).order_by(Entity.name.asc()).limit(300).all()

    candidates: list[dict[str, Any]] = []
    visited: set[tuple[int, int]] = set()

    for i in range(len(entities)):
        e1 = entities[i]
        for j in range(i + 1, len(entities)):
            e2 = entities[j]
            pair_key = (min(e1.id, e2.id), max(e1.id, e2.id))
            if pair_key in visited:
                continue

            ratio = difflib.SequenceMatcher(None, e1.name.lower(), e2.name.lower()).ratio()
            if ratio >= threshold and e1.name.lower() != e2.name.lower():
                visited.add(pair_key)
                candidates.append(
                    {
                        "entity_1": {"id": e1.id, "name": e1.name, "slug": e1.slug, "type": e1.entity_type},
                        "entity_2": {"id": e2.id, "name": e2.name, "slug": e2.slug, "type": e2.entity_type},
                        "similarity_pct": int(ratio * 100),
                    }
                )
                if len(candidates) >= limit:
                    return candidates

    return candidates


@taxonomy_bp.route("/")
@admin_required
def index():
    """Render taxonomy overview with sections, categories, popular entities, and merge suggestions."""
    sections = TaxonomyRepository.get_sections(active_only=False)
    categories = db.session.query(Category).order_by(Category.name.asc()).all()
    popular_entities = TaxonomyRepository.get_popular_entities(limit=30)
    sources = db.session.query(Source).order_by(Source.name.asc()).all()
    merge_candidates = find_duplicate_entities(threshold=0.82, limit=15)

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
