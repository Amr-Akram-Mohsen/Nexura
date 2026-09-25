"""
Nexura Phase 7 — Content Lifecycle & Editorial Readiness Service (§9.2, §25)
Implements:
1. Publishing lifecycle transitions (publish, unpublish, archive) with cascaded invalidation.
2. 5-Dimension Editorial Publishing Readiness Index (0–100 score) (§9.2).
3. Holistic Content Score computation.
"""
from __future__ import annotations
import logging
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.caching import invalidate_content_after_write
from app.models.content import Content, Article, ArticleSource, Author, ContentEntity
from app.models.video import Video
from app.models.source import Source
from app.repositories.content_repo import ContentRepository

log = logging.getLogger(__name__)


def evaluate_editorial_readiness(article_id: int) -> dict[str, Any]:
    """
    Evaluates 5-dimension Publishing Readiness Index (0–100 score) (Phase 7 §9.2):
    1. Core Metadata (25 pts): valid title, non-empty description/summary
    2. Body & Extraction (30 pts): word count >= 150, scraped HTML body present
    3. Taxonomy Mapping (20 pts): Category assigned, >= 2 Entity tags linked
    4. Media Assets (15 pts): Valid high-res thumbnail / header image
    5. Source Attribution (10 pts): Known publisher, source authority >= 40
    """
    article = db.session.query(Article).filter(Article.id == article_id).first()
    if not article:
        return {"score": 0, "tier": "Not Ready", "breakdown": {}}

    content = (
        db.session.query(Content)
        .options(
            joinedload(Content.category),
            joinedload(Content.source),
            selectinload(Content.content_entities),
        )
        .filter(Content.object_type == "article", Content.object_id == article_id)
        .first()
    )

    pts_metadata = 0
    pts_body = 0
    pts_taxonomy = 0
    pts_media = 0
    pts_source = 0

    # 1. Core Metadata (25 pts)
    if article.title and len(article.title.strip()) >= 5:
        pts_metadata += 15
    if (article.description and len(article.description.strip()) >= 10) or (article.summary and len(article.summary.strip()) >= 10):
        pts_metadata += 10

    # 2. Body & Extraction (30 pts)
    words = article.word_count or 0
    if words >= 250:
        pts_body += 20
    elif words >= 150:
        pts_body += 10

    if article.content_html and len(article.content_html.strip()) >= 50:
        pts_body += 10

    # 3. Taxonomy Mapping (20 pts)
    if content and content.category_id:
        pts_taxonomy += 10
    entity_count = len(content.content_entities) if content and content.content_entities else 0
    if entity_count >= 2:
        pts_taxonomy += 10
    elif entity_count >= 1:
        pts_taxonomy += 5

    # 4. Media Assets (15 pts)
    if article.image_url and article.image_url.startswith("http"):
        pts_media += 15

    # 5. Source Attribution (10 pts)
    if content and content.source:
        pts_source += 5
        if (content.source.authority_score or 0) >= 40:
            pts_source += 5

    total_score = pts_metadata + pts_body + pts_taxonomy + pts_media + pts_source

    if total_score >= 80:
        tier = "Ready"
    elif total_score >= 60:
        tier = "Almost Ready"
    elif total_score >= 40:
        tier = "Needs Work"
    else:
        tier = "Not Ready"

    return {
        "score": total_score,
        "tier": tier,
        "breakdown": {
            "core_metadata": pts_metadata,
            "body_extraction": pts_body,
            "taxonomy_mapping": pts_taxonomy,
            "media_assets": pts_media,
            "source_attribution": pts_source,
        },
    }


class ContentService:
    """Service layer managing content lifecycle, scoring, and readiness evaluation."""

    @staticmethod
    def publish_content(content_id: int) -> bool:
        """Publish a content item and trigger cascaded cache invalidation."""
        content = db.session.get(Content, content_id)
        if not content:
            return False

        content.is_published = True
        content.is_active = True
        content.published_at = content.published_at or datetime.now(timezone.utc)

        if content.object_type == "article":
            article = db.session.get(Article, content.object_id)
            if article:
                article.status = "published"

        db.session.commit()
        invalidate_content_after_write(content_id)
        return True

    @staticmethod
    def unpublish_content(content_id: int) -> bool:
        """Unpublish a content item and invalidate cache."""
        content = db.session.get(Content, content_id)
        if not content:
            return False

        content.is_published = False
        db.session.commit()
        invalidate_content_after_write(content_id)
        return True

    @staticmethod
    def archive_content(content_id: int) -> bool:
        """Archive a content item (deactivate and unpublish)."""
        content = db.session.get(Content, content_id)
        if not content:
            return False

        content.is_published = False
        content.is_active = False

        if content.object_type == "article":
            article = db.session.get(Article, content.object_id)
            if article:
                article.status = "archived"

        db.session.commit()
        invalidate_content_after_write(content_id)
        return True

    @staticmethod
    def calculate_content_score(content: Content) -> float:
        """
        Recalculate holistic content score:
        Base = Quality * 0.4 + ln(1 + Views) * 0.3 + Reactions * 0.2 + Freshness * 0.1
        """
        quality = 50.0
        if content.object_type == "article":
            readiness = evaluate_editorial_readiness(content.object_id)
            quality = float(readiness["score"])

        views = max(0, content.view_count or 0)
        pop_term = math.log(1.0 + views) * 5.0
        engagement_term = (
            ((content.like_count or 0) * 2.0)
            + ((content.save_count or 0) * 3.0)
            + ((content.comment_count or 0) * 2.5)
        )

        freshness_term = 10.0
        if content.published_at:
            now = datetime.now(timezone.utc)
            pub = content.published_at
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            days = max(0.0, (now - pub).total_seconds() / 86400.0)
            freshness_term = 10.0 / (1.0 + (days / 30.0))

        score = (quality * 0.4) + (pop_term * 0.3) + (engagement_term * 0.2) + (freshness_term * 0.1)
        content.score = round(score, 2)
        db.session.commit()
        return content.score

    @staticmethod
    def get_slug(content: Content) -> str:
        """Return URL-safe slug for a content item."""
        return content.slug

    @staticmethod
    def get_slug_id(content: Content) -> str:
        """Return unique slug identifier (e.g. 123-my-article-title)."""
        return content.slug_id

    @staticmethod
    def parse_content_id(slug_or_id: str | int | None) -> int | None:
        """Extract integer content ID from either a pure ID or slugified string (e.g. 123-my-title)."""
        if slug_or_id is None:
            return None
        if isinstance(slug_or_id, int):
            return slug_or_id
        s = str(slug_or_id).strip()
        if s.isdigit():
            return int(s)
        prefix = s.split("-", 1)[0]
        if prefix.isdigit():
            return int(prefix)
        return None

