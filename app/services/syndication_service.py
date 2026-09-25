"""
Nexura Phase 7 — Multichannel Content Syndication Service (§20)
Implements:
1. Rule-based platform draft generator (YouTube, Pinterest, Instagram, TikTok, Twitter/X, LinkedIn).
2. Platform Engagement Index computation: Index = 2.0*Likes + 5.0*Clicks + 10.0*Shares + 0.1*Views.
3. Distribution post scheduling and management.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func

from app.extensions import db
from app.models.content import Content, Article
from app.models.distribution import DistributionPlatform, DistributionPost

log = logging.getLogger(__name__)


def calculate_platform_engagement_index(
    likes: int, clicks: int, shares: int, views: int
) -> float:
    """
    Computes weighted channel effectiveness score (Phase 7 §20):
    Index = 2.0*Likes + 5.0*Clicks + 10.0*Shares + 0.1*Views
    """
    return round((2.0 * likes) + (5.0 * clicks) + (10.0 * shares) + (0.1 * views), 2)


class SyndicationService:
    """Service layer for multi-channel social draft generation and distribution tracking."""

    @staticmethod
    def generate_drafts_for_article(content_id: int) -> dict[str, Any]:
        """
        Transforms an article into platform-specific social drafts (Phase 7 §20).
        """
        content = db.session.get(Content, content_id)
        if not content:
            return {}

        article = db.session.get(Article, content.object_id) if content.object_type == "article" else None
        title = content.title or "Tech Update"
        summary = article.summary if article and article.summary else (content.preview_text or title)
        source_name = content.source.name if content.source else "Nexura"
        tags = [ce.entity.name for ce in content.content_entities if ce.entity]
        hashtag_str = " ".join([f"#{t.replace(' ', '')}" for t in tags[:4]]) if tags else "#Tech #Innovation #Nexura"

        slug_id = content.slug_id
        target_path = f"{content.object_type}/{slug_id}"

        drafts = {
            "twitter": {
                "platform": "Twitter / X",
                "character_limit": 280,
                "text": f"🔥 {title}\n\n{summary[:140]}...\n\nRead more on Nexura: https://nexura.tech/{target_path}\n\n{hashtag_str}",
            },
            "linkedin": {
                "platform": "LinkedIn",
                "text": f"💡 Industry Insight: {title}\n\n{summary}\n\nKey takeaways:\n• Breakdown of core trends\n• Practical analysis for builders & creators\n\nFull analysis: https://nexura.tech/{target_path}\n\n{hashtag_str}",
            },
            "youtube": {
                "platform": "YouTube (Script & Description)",
                "hook": f"Did you know about {title}? Here is what you need to know in under 60 seconds.",
                "outline": [
                    {"time": "0:00", "topic": "Hook & Headline"},
                    {"time": "0:15", "topic": "Key Feature / Breaking Development"},
                    {"time": "0:40", "topic": "Why It Matters & Final Verdict"},
                ],
                "description": f"{title}\n\n{summary}\n\nOriginally published on Nexura: https://nexura.tech/{target_path}\n\n{hashtag_str}",
            },
            "pinterest": {
                "platform": "Pinterest (Cheat Sheet)",
                "pin_title": title[:100],
                "description": f"Visual breakdown: {title}. {summary[:200]} Save this pin for later! {hashtag_str}",
            },
            "instagram": {
                "platform": "Instagram / Threads",
                "caption": f"✨ {title}\n.\n{summary}\n.\n💬 What are your thoughts on this? Let us know below!\n.\n🔗 Link in bio to read full breakdown.\n.\n{hashtag_str}",
            },
            "tiktok": {
                "platform": "TikTok (Shorts Script)",
                "hook": f"Stop scrolling! Here is the truth about {title}.",
                "talking_points": [
                    "Point 1: The core announcement or review score",
                    "Point 2: The biggest surprise / pro & con",
                    "Point 3: Who this is actually for",
                ],
            },
        }

        return drafts

    @staticmethod
    def get_syndication_stats() -> dict[str, Any]:
        """Fetch overall social syndication reach metrics."""
        posts = (
            db.session.query(DistributionPost)
            .order_by(desc(DistributionPost.created_at))
            .limit(30)
            .all()
        )

        total_posts = db.session.query(func.count(DistributionPost.id)).scalar() or 0
        total_views = db.session.query(func.coalesce(func.sum(DistributionPost.views_count), 0)).scalar() or 0
        total_clicks = db.session.query(func.coalesce(func.sum(DistributionPost.clicks_count), 0)).scalar() or 0
        total_shares = db.session.query(func.coalesce(func.sum(DistributionPost.shares_count), 0)).scalar() or 0
        total_likes = db.session.query(func.coalesce(func.sum(DistributionPost.likes_count), 0)).scalar() or 0

        engagement_index = calculate_platform_engagement_index(
            likes=int(total_likes),
            clicks=int(total_clicks),
            shares=int(total_shares),
            views=int(total_views),
        )

        return {
            "posts": posts,
            "total_posts": total_posts,
            "total_views": int(total_views),
            "total_clicks": int(total_clicks),
            "total_shares": int(total_shares),
            "total_likes": int(total_likes),
            "engagement_index": engagement_index,
        }
