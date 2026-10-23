"""Content lifecycle, editorial readiness evaluation, and scoring service."""

from __future__ import annotations
import logging
import math
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db, cache
from app.caching import invalidate_content_after_write, CACHE_TTL_CONTENT_PAGE
from app.models.content import Content, Article, ArticleSource, Author, ContentEntity
from app.models.video import Video
from app.models.source import Source
from app.repositories.content_repo import ContentRepository
from app.repositories.article_repo import ArticleRepository
from app.repositories.video_repo import VideoRepository
from app.services.recommendation_service import RecommendationService
from app.serializers.content_serializers import serialize_content_card, _format_duration

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

    @staticmethod
    def get_detail_page_data(content_id: int, expected_type: str) -> dict[str, Any] | None:
        """Fetch and assemble cached detail page data for an article or video."""
        cache_key = f"content_page_{content_id}"
        page_data = cache.get(cache_key)
        if page_data is not None:
            return page_data

        content = ContentRepository.get_published_content(content_id)
        if not content or content.object_type != expected_type:
            return None

        related_entries = RecommendationService.get_related_recommendations_with_reasons(content_id, limit=6)
        if not related_entries:
            fallback = ContentRepository.get_related_content(content_id, limit=6)
            related_entries = [(item, "Related story") for item in fallback]

        serialized_related = []
        for rel_content, rel_reason in related_entries:
            card = serialize_content_card(rel_content)
            if rel_reason:
                card["recommendation_reason"] = rel_reason
            serialized_related.append(card)

        section_slug = content.section.slug if content.section else None
        section_name = content.section.name if content.section else None
        category_slug = content.category.slug if content.category else None
        category_name = content.category.name if content.category else None

        formatted_date = content.published_at.strftime("%b %d, %Y") if content.published_at else ""
        formatted_date_long = content.published_at.strftime("%B %d, %Y") if content.published_at else ""
        published_iso = content.published_at.isoformat() if content.published_at else ""

        if expected_type == "article":
            article_obj = ArticleRepository.get_by_id(content.object_id)
            if not article_obj:
                return None

            title = article_obj.title or content.title or ""
            reading_time = ((int(article_obj.word_count) // 200) + 1) if (article_obj.word_count and article_obj.word_count > 0) else None
            reading_time_text = f"{reading_time} min read" if reading_time else None

            # Shared breadcrumbs
            breadcrumbs = [{"name": "Home", "url": "/"}]
            if section_name and section_slug:
                breadcrumbs.append({"name": section_name, "url": f"/{section_slug}"})
            if category_name and category_slug and section_slug:
                breadcrumbs.append({"name": category_name, "url": f"/{section_slug}/{category_slug}"})
            truncated_title = (title[:47] + "...") if len(title) > 50 else title
            breadcrumbs.append({"name": truncated_title})

            source_obj = ContentRepository.get_source_by_id(content.source_id) if content.source_id else None
            page_data = {
                "content": content,
                "article": article_obj,
                "authors": ArticleRepository.get_authors(article_obj.id),
                "source": source_obj,
                "entities": ContentRepository.get_entities_for_content(content_id),
                "related": serialized_related,
                "section_slug": section_slug,
                "section_name": section_name,
                "category_slug": category_slug,
                "category_name": category_name,
                "formatted_date": formatted_date,
                "formatted_date_long": formatted_date_long,
                "published_iso": published_iso,
                "reading_time": reading_time,
                "reading_time_text": reading_time_text,
                "breadcrumbs": breadcrumbs,
            }
        elif expected_type == "video":
            video_obj = VideoRepository.get_by_id(content.object_id)
            if not video_obj:
                return None

            title = video_obj.title or content.title or ""

            # Shared breadcrumbs
            breadcrumbs = [{"name": "Home", "url": "/"}]
            if section_name and section_slug:
                breadcrumbs.append({"name": section_name, "url": f"/{section_slug}"})
            if category_name and category_slug and section_slug:
                breadcrumbs.append({"name": category_name, "url": f"/{section_slug}/{category_slug}"})
            truncated_title = (title[:47] + "...") if len(title) > 50 else title
            breadcrumbs.append({"name": truncated_title})

            page_data = {
                "content": content,
                "video": video_obj,
                "yt_comments": VideoRepository.get_top_comments(video_obj.id, limit=15),
                "related": serialized_related,
                "duration_formatted": _format_duration(video_obj.duration_seconds),
                "section_slug": section_slug,
                "section_name": section_name,
                "category_slug": category_slug,
                "category_name": category_name,
                "formatted_date": formatted_date,
                "formatted_date_long": formatted_date_long,
                "published_iso": published_iso,
                "breadcrumbs": breadcrumbs,
            }
        else:
            return None

        cache.set(cache_key, page_data, timeout=CACHE_TTL_CONTENT_PAGE)
        return page_data
