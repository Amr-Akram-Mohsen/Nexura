"""
Nexura Phase 7 — Admin Contents Controller (§18.2, §18.3, §9.2)
Handles:
1. Multi-facet filterable content inventory table with pagination.
2. 5-Dimension Editorial Readiness Inspector (/inspect/<id>).
3. 1-Click batch actions (Publish, Unpublish, Activate, Deactivate, Delete).
"""
from __future__ import annotations
import logging
import math
from typing import Any

from flask import (
    Blueprint, abort, jsonify, render_template, request,
)
from sqlalchemy import func, desc
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.caching import invalidate_content_after_write
from app.models.content import Content, Article, ContentEntity
from app.models.video import Video
from app.models.taxonomy import Section, Category
from app.models.source import Source
from app.repositories.content_repo import ContentRepository
from app.services.content_service import evaluate_editorial_readiness
from app.routes.admin import admin_required

log = logging.getLogger(__name__)

contents_bp = Blueprint("contents", __name__)


@contents_bp.route("/")
@admin_required
def index():
    """
    Content Inventory Table with multi-faceted filtering (Phase 7 §18.2).
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 30, type=int)
    q = request.args.get("q", "").strip()
    object_type = request.args.get("type")
    section_id = request.args.get("section_id", type=int)
    category_id = request.args.get("category_id", type=int)
    is_published = request.args.get("is_published")
    status = request.args.get("status")

    query = (
        db.session.query(Content)
        .options(
            joinedload(Content.section),
            joinedload(Content.category),
            joinedload(Content.source),
            selectinload(Content.content_entities).joinedload(ContentEntity.entity),
        )
    )

    if q:
        query = query.filter(Content.title.ilike(f"%{q}%"))

    if object_type in ("article", "video"):
        query = query.filter(Content.object_type == object_type)

    if section_id:
        query = query.filter(Content.section_id == section_id)

    if category_id:
        query = query.filter(Content.category_id == category_id)

    if is_published == "true":
        query = query.filter(Content.is_published.is_(True))
    elif is_published == "false":
        query = query.filter(Content.is_published.is_(False))

    total = query.with_entities(func.count(Content.id)).scalar() or 0
    offset = max(0, (page - 1) * per_page)
    items = (
        query.order_by(desc(Content.id))
        .offset(offset)
        .limit(per_page)
        .all()
    )

    ContentRepository.resolve_polymorphic_payloads(items)

    sections = db.session.query(Section).order_by(Section.name.asc()).all()
    categories = db.session.query(Category).order_by(Category.name.asc()).all()
    total_pages = max(1, math.ceil(total / per_page))

    return render_template(
        "admin/contents.html",
        items=items,
        sections=sections,
        categories=categories,
        total=total,
        page=page,
        total_pages=total_pages,
        q=q,
        active_tab="contents",
    )


@contents_bp.route("/inspect/<int:content_id>")
@admin_required
def inspect(content_id: int):
    """
    Editorial Inspection & Readiness Breakdown (Phase 7 §18.3, §9.2).
    Displays 5-dimension quality readiness score and Diffbot body health.
    """
    content = ContentRepository.get_by_id(content_id, published_only=False)
    if not content:
        abort(404)

    ContentRepository.resolve_polymorphic_payloads([content])

    readiness = None
    if content.object_type == "article":
        readiness = evaluate_editorial_readiness(content.object_id)

    return render_template(
        "admin/inspect.html",
        content=content,
        readiness=readiness,
        active_tab="contents",
    )


@contents_bp.route("/batch", methods=["POST"])
@admin_required
def batch_action():
    """
    1-Click batch actions (Phase 7 §18.2):
    Actions: publish, unpublish, activate, deactivate, delete.
    """
    action = request.form.get("action", "").strip().lower()
    content_ids_raw = request.form.getlist("content_ids") or (request.json.get("content_ids", []) if request.is_json else [])

    content_ids = []
    for cid in content_ids_raw:
        try:
            content_ids.append(int(cid))
        except (TypeError, ValueError):
            pass

    if not content_ids:
        return jsonify({"success": False, "message": "No items selected."}), 400

    count = 0
    if action == "publish":
        count = (
            db.session.query(Content)
            .filter(Content.id.in_(content_ids))
            .update({"is_published": True, "is_active": True}, synchronize_session=False)
        )
        # Also update underlying articles
        article_ids = [
            r[0] for r in db.session.query(Content.object_id)
            .filter(Content.id.in_(content_ids), Content.object_type == "article").all()
        ]
        if article_ids:
            db.session.query(Article).filter(Article.id.in_(article_ids)).update(
                {"status": "published"}, synchronize_session=False
            )

    elif action == "unpublish":
        count = (
            db.session.query(Content)
            .filter(Content.id.in_(content_ids))
            .update({"is_published": False}, synchronize_session=False)
        )

    elif action == "deactivate":
        count = (
            db.session.query(Content)
            .filter(Content.id.in_(content_ids))
            .update({"is_active": False, "is_published": False}, synchronize_session=False)
        )

    elif action == "activate":
        count = (
            db.session.query(Content)
            .filter(Content.id.in_(content_ids))
            .update({"is_active": True}, synchronize_session=False)
        )

    elif action == "delete":
        count = (
            db.session.query(Content)
            .filter(Content.id.in_(content_ids))
            .delete(synchronize_session=False)
        )

    else:
        return jsonify({"success": False, "message": f"Unknown action '{action}'."}), 400

    db.session.commit()

    # Invalidate cache for all affected items
    for cid in content_ids:
        invalidate_content_after_write(cid)

    return jsonify({
        "success": True,
        "action": action,
        "count": count,
        "message": f"Successfully performed '{action}' on {count} item(s).",
    })
