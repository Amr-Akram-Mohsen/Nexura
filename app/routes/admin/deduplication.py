"""Admin deduplication workbench controller for cross-source duplicate detection and canonicalization."""

from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import desc

from app.extensions import db
from app.caching import invalidate_content_after_write
from app.models.content import Content, Article, ArticleSource
from app.ingestion.normalizer import normalize_title, jaccard_similarity
from app.routes.admin import admin_required

log = logging.getLogger(__name__)

deduplication_bp = Blueprint("deduplication", __name__)


def find_duplicate_clusters(days: int = 7, threshold: float = 0.85) -> list[dict[str, Any]]:
    """Scan rolling window of articles to detect duplicate clusters across sources."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    articles = (
        db.session.query(Article)
        .join(Content, Content.object_id == Article.id)
        .filter(Content.object_type == "article", Content.published_at >= cutoff)
        .order_by(Article.id.asc())
        .all()
    )

    token_map = [(a, set(normalize_title(a.title))) for a in articles]
    clusters: list[dict[str, Any]] = []
    visited: set[int] = set()

    for i in range(len(token_map)):
        a1, tokens1 = token_map[i]
        if a1.id in visited or not tokens1:
            continue

        cluster_articles = [a1]

        for j in range(i + 1, len(token_map)):
            a2, tokens2 = token_map[j]
            if a2.id in visited or not tokens2:
                continue

            sim = jaccard_similarity(tokens1, tokens2)
            if sim >= threshold:
                cluster_articles.append(a2)
                visited.add(a2.id)

        if len(cluster_articles) > 1:
            visited.add(a1.id)
            canonical = cluster_articles[0]
            clusters.append(
                {"canonical": canonical, "duplicates": cluster_articles[1:], "total_count": len(cluster_articles), "similarity_pct": int(threshold * 100)}
            )

    return clusters


@deduplication_bp.route("/")
@admin_required
def index():
    """Render deduplication workbench UI with identified duplicate clusters."""
    clusters = find_duplicate_clusters(days=7, threshold=0.85)
    return render_template("admin/deduplication.html", clusters=clusters, active_tab="deduplication")


@deduplication_bp.route("/resolve", methods=["POST"])
@admin_required
def resolve_cluster():
    """Consolidate duplicate cluster into canonical article and archive duplicates."""
    canonical_id = request.form.get("canonical_id", type=int)
    duplicate_ids_raw = request.form.getlist("duplicate_ids")

    if not canonical_id:
        return jsonify({"success": False, "message": "Missing canonical ID."}), 400

    canonical_article = db.session.get(Article, canonical_id)
    if not canonical_article:
        return jsonify({"success": False, "message": "Canonical article not found."}), 404

    duplicate_ids = []
    for did in duplicate_ids_raw:
        try:
            duplicate_ids.append(int(did))
        except (TypeError, ValueError):
            pass

    resolved_count = 0
    canonical_content = db.session.query(Content).filter(Content.object_type == "article", Content.object_id == canonical_id).first()

    for dup_id in duplicate_ids:
        dup_article = db.session.get(Article, dup_id)
        if not dup_article or dup_article.id == canonical_id:
            continue

        if dup_article.canonical_url:
            existing_src = (
                db.session.query(ArticleSource).filter(ArticleSource.article_id == canonical_id, ArticleSource.url == dup_article.canonical_url).first()
            )
            if not existing_src:
                dup_source = db.session.query(Content.source_id).filter(Content.object_type == "article", Content.object_id == dup_article.id).scalar()
                if dup_source:
                    new_link = ArticleSource(article_id=canonical_id, source_id=dup_source, url=dup_article.canonical_url)
                    db.session.add(new_link)

        dup_content = db.session.query(Content).filter(Content.object_type == "article", Content.object_id == dup_article.id).first()
        if dup_content:
            dup_content.is_published = False
            dup_content.is_active = False
            invalidate_content_after_write(dup_content.id)

        dup_article.status = "archived"
        resolved_count += 1

    db.session.commit()
    if canonical_content:
        invalidate_content_after_write(canonical_content.id)
    else:
        invalidate_content_after_write()

    return jsonify({"success": True, "resolved_count": resolved_count, "message": f"Successfully merged and canonicalized {resolved_count} duplicate stories."})
