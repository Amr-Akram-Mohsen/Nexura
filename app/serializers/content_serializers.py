"""
Nexura Phase 7 — Content & Taxonomy DTO Serializers
Phase 7 §22: ORM entities never cross directly into templates or JSON responses.
All payloads are compacted via compact_dict to eliminate nulls/empty collections.
"""
from __future__ import annotations
from typing import Any

from app.serializers.utils import compact_dict


def _format_duration(seconds: int | None) -> str | None:
    if not seconds:
        return None
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}:{secs:02d}"


def _reading_time(word_count: int | None) -> int | None:
    """Estimated reading time in minutes at 200 WPM."""
    if not word_count:
        return None
    return max(1, round(word_count / 200))


def serialize_content_card(content, *, include_article: bool = True) -> dict[str, Any]:
    """
    Lightweight card payload for listing, feed, category, and search results.
    Returns: title, slug/id, thumbnail, reading_time, top 7 entity tags.
    """
    result: dict[str, Any] = {
        "id": content.id,
        "object_type": content.object_type,
        "object_id": content.object_id,
        "title": content.title,
        "preview_text": content.preview_text,
        "published_at": content.published_at.isoformat() if content.published_at else None,
        "formatted_date": content.published_at.strftime('%b %d, %Y') if content.published_at else None,
        "age": content.published_at.strftime('%b %d, %Y') if content.published_at else None,
        "view_count": content.view_count or 0,
        "like_count": content.like_count or 0,
        "score": content.score or 0.0,
        "section": {
            "id": content.section_id,
            "name": content.section.name if content.section else None,
            "slug": content.section.slug if content.section else None,
        } if content.section else None,
        "category": {
            "id": content.category_id,
            "name": content.category.name if content.category else None,
            "slug": content.category.slug if content.category else None,
        } if content.category else None,
        "source": {
            "name": content.source.name if content.source else None,
            "slug": content.source.slug if content.source else None,
            "logo_url": content.source.logo_url if content.source else None,
        } if content.source else None,
        "entities": [
            {
                "id": ce.entity.id,
                "name": ce.entity.name,
                "slug": ce.entity.slug,
                "type": ce.entity.entity_type,
            }
            for ce in sorted(
                content.content_entities or [],
                key=lambda e: e.relevance_score or 0,
                reverse=True,
            )[:7]
            if ce.entity
        ],
    }

    article_obj = getattr(content, "_article_obj", None)
    video_obj = getattr(content, "_video_obj", None)

    # Flattened properties for card macro compatibility
    thumbnail = None
    reading_time = None
    duration = None
    channel_name = None

    if content.object_type == "article":
        if article_obj:
            thumbnail = article_obj.image_url
            reading_time = _reading_time(article_obj.word_count)
            if include_article:
                result["article"] = {
                    "image_url": article_obj.image_url,
                    "word_count": article_obj.word_count,
                    "reading_time": reading_time,
                    "language": article_obj.language,
                    "status": article_obj.status,
                }
    elif content.object_type == "video":
        if video_obj:
            thumbnail = video_obj.thumbnail_url
            duration = _format_duration(video_obj.duration_seconds)
            channel_name = video_obj.channel_name
            result["video"] = {
                "external_id": video_obj.external_id,
                "platform": video_obj.platform,
                "thumbnail_url": video_obj.thumbnail_url,
                "duration": duration,
                "channel_name": channel_name,
                "creator": video_obj.creator,
                "view_count": video_obj.view_count or 0,
            }

    result["thumbnail"] = thumbnail
    result["preview"] = content.preview_text
    result["reading_time"] = reading_time
    result["duration"] = duration
    result["source_name"] = content.source.name if content.source else channel_name
    result["source_logo"] = content.source.logo_url if content.source else None
    result["category_name"] = content.category.name if content.category else None
    result["category_slug"] = content.category.slug if content.category else None
    result["section_name"] = content.section.name if content.section else None
    result["section_slug"] = content.section.slug if content.section else None
    result["tags"] = result.get("entities", [])
    result["channel_name"] = channel_name
    result["tags"] = result.get("entities", [])

    return compact_dict(result)


def serialize_content_detail(content, *, article=None, video=None) -> dict[str, Any]:
    """
    Full detail payload for article/video detail pages.
    Includes: HTML body, authors, source authority, grouped entities.
    """
    base = serialize_content_card(content, include_article=False)
    base["comment_count"] = content.comment_count or 0
    base["save_count"] = content.save_count or 0
    base["dislike_count"] = content.dislike_count or 0
    base["share_count"] = content.share_count or 0
    base["review_score"] = content.review_score or 0.0
    base["review_count"] = content.review_count or 0

    if article:
        base["article"] = {
            "content_html": article.content_html,
            "content_text": article.content_text,
            "summary": article.summary,
            "description": article.description,
            "image_url": article.image_url,
            "word_count": article.word_count,
            "reading_time": _reading_time(article.word_count),
            "language": article.language,
            "status": article.status,
            "canonical_url": article.canonical_url,
            "sentiment_score": article.sentiment_score,
            "authors": [
                {
                    "id": a.id,
                    "name": a.name,
                    "slug": a.slug,
                    "icon_url": a.icon_url,
                    "is_agency": a.is_agency,
                }
                for a in (article.authors or [])
            ],
            "primary_source": {
                "id": article.primary_source.id,
                "url": article.primary_source.url,
                "source": {
                    "name": article.primary_source.source.name,
                    "slug": article.primary_source.source.slug,
                    "domain": article.primary_source.source.domain,
                    "authority_score": article.primary_source.source.authority_score,
                } if article.primary_source.source else None,
            } if article.primary_source else None,
        }

    if video:
        base["video"] = {
            "external_id": video.external_id,
            "platform": video.platform,
            "thumbnail_url": video.thumbnail_url,
            "duration": _format_duration(video.duration_seconds),
            "channel_name": video.channel_name,
            "channel_id": video.channel_id,
            "creator": video.creator,
            "description": video.description,
            "description_display_rule": video.description_display_rule,
            "view_count": video.view_count or 0,
            "like_count": video.like_count or 0,
            "comments_count": video.comments_count or 0,
            "comments": [
                {
                    "id": vc.id,
                    "author_name": vc.author_name,
                    "text": vc.text,
                    "like_count": vc.like_count,
                    "published_at": vc.published_at.isoformat() if vc.published_at else None,
                }
                for vc in (video.video_comments or [])[:20]
            ],
        }

    # Group entities by type (brand, topic, organization, person, etc.)
    entity_groups: dict[str, list] = {}
    for ce in (content.content_entities or []):
        if not ce.entity:
            continue
        etype = ce.entity.entity_type or "other"
        entity_groups.setdefault(etype, []).append({
            "id": ce.entity.id,
            "name": ce.entity.name,
            "slug": ce.entity.slug,
            "image_url": ce.entity.image_url,
        })
    base["entity_groups"] = entity_groups

    return compact_dict(base)


def serialize_section(section) -> dict[str, Any]:
    """Serialize Section model to DTO."""
    return compact_dict({
        "id": section.id,
        "name": section.name,
        "slug": section.slug,
        "description": section.description,
        "allowed_filters": section.allowed_filters or {},
        "sort_order": section.sort_order,
    })


def serialize_category(category) -> dict[str, Any]:
    """Serialize Category model to DTO."""
    return compact_dict({
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "parent_id": category.parent_id,
        "is_leaf": category.is_leaf,
        "parent": {
            "name": category.parent.name,
            "slug": category.parent.slug,
        } if category.parent else None,
    })


def serialize_entity(entity, content_count: int | None = None) -> dict[str, Any]:
    """Serialize Entity model to DTO."""
    return compact_dict({
        "id": entity.id,
        "name": entity.name,
        "slug": entity.slug,
        "entity_type": entity.entity_type,
        "image_url": entity.image_url,
        "description": entity.description,
        "wikidata_id": entity.wikidata_id,
        "wikipedia_url": entity.wikipedia_url,
        "content_count": content_count,
    })
