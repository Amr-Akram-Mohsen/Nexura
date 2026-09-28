"""Content lifecycle, editorial readiness evaluation, and scoring service."""

from __future__ import annotations
import logging
import math
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.caching import invalidate_content_after_write
from app.models.content import Content, Article, ArticleSource, Author, ContentEntity
from app.models.video import Video
from app.models.source import Source
from app.repositories.content_repo import ContentRepository

log = logging.getLogger(__name__)


@dataclass
class ReadinessResult:
    """Editorial Publishing Readiness Index result."""

    total: int
    core_metadata: int
    body_extraction: int
    taxonomy_mapping: int
    media_assets: int
    source_attribution: int

    @property
    def score(self) -> int:
        return self.total

    @property
    def tier(self) -> str:
        if self.total >= 80:
            return "Ready"
        if self.total >= 60:
            return "Almost Ready"
        if self.total >= 40:
            return "Needs Work"
        return "Not Ready"

    @property
    def tier_class(self) -> str:
        return {"Ready": "success", "Almost Ready": "warning", "Needs Work": "warning", "Not Ready": "danger"}[self.tier]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.total,
            "tier": self.tier,
            "tier_class": self.tier_class,
            "breakdown": {
                "core_metadata": self.core_metadata,
                "body_extraction": self.body_extraction,
                "taxonomy_mapping": self.taxonomy_mapping,
                "media_assets": self.media_assets,
                "source_attribution": self.source_attribution,
            },
        }


def compute_readiness(article: Any, content: Any) -> ReadinessResult:
    """Compute 5-dimension Editorial Readiness Index (0-100 score)."""
    pts_metadata = 0
    pts_body = 0
    pts_taxonomy = 0
    pts_media = 0
    pts_source = 0

    if article:
        if getattr(article, "title", None) and len(str(article.title).strip()) >= 5:
            pts_metadata += 15
        desc = getattr(article, "description", None) or ""
        summ = getattr(article, "summary", None) or ""
        if len(str(desc).strip()) >= 10 or len(str(summ).strip()) >= 10:
            pts_metadata += 10

        words = getattr(article, "word_count", 0) or 0
        if words >= 250:
            pts_body += 20
        elif words >= 150:
            pts_body += 10

        html_body = getattr(article, "content_html", None) or ""
        if len(str(html_body).strip()) >= 50:
            pts_body += 10

        img = getattr(article, "image_url", None) or ""
        if str(img).startswith("http"):
            pts_media += 15

    if content:
        if getattr(content, "category_id", None):
            pts_taxonomy += 10
        entities = getattr(content, "content_entities", None)
        entity_count = len(entities) if entities is not None else 0
        if entity_count >= 2:
            pts_taxonomy += 10
        elif entity_count >= 1:
            pts_taxonomy += 5

        source = getattr(content, "source", None)
        if source:
            pts_source += 5
            if (getattr(source, "authority_score", 0) or 0) >= 40:
                pts_source += 5

    total = min(pts_metadata + pts_body + pts_taxonomy + pts_media + pts_source, 100)
    return ReadinessResult(
        total=total, core_metadata=pts_metadata, body_extraction=pts_body, taxonomy_mapping=pts_taxonomy, media_assets=pts_media, source_attribution=pts_source
    )


def evaluate_editorial_readiness(article_id: int) -> dict[str, Any]:
    """Evaluate publishing readiness score and breakdown for an article ID."""
    article = db.session.query(Article).filter(Article.id == article_id).first()
    if not article:
        return {"score": 0, "tier": "Not Ready", "breakdown": {}}

    content = (
        db.session.query(Content)
        .options(joinedload(Content.category), joinedload(Content.source), selectinload(Content.content_entities))
        .filter(Content.object_type == "article", Content.object_id == article_id)
        .first()
    )

    return compute_readiness(article, content).to_dict()


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
        """Calculate and store composite content score."""
        quality = 50.0
        if content.object_type == "article":
            readiness = evaluate_editorial_readiness(content.object_id)
            quality = float(readiness["score"])

        views = max(0, content.view_count or 0)
        pop_term = math.log(1.0 + views) * 5.0
        engagement_term = ((content.like_count or 0) * 2.0) + ((content.save_count or 0) * 3.0) + ((content.comment_count or 0) * 2.5)

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
        """Extract integer content ID from either a pure ID or slugified string."""
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
