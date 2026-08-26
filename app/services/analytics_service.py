"""
Nexura Phase 7 — Analytics & Closed-Loop Intelligence Service (§17)
Implements:
1. Demand vs. Supply Opportunity Matrix (§17.1).
2. 7-Day & 14-Day Engagement Momentum Velocity (§17.2).
3. Content Traffic Decay Detection (§17.3).
4. Closed-Loop Performance & CTR Feedback (§17.4).
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import desc, func, and_, or_

from app.extensions import db
from app.models.content import Content, ContentEntity
from app.models.taxonomy import Category, Entity
from app.models.interaction import View, Save, Reaction, Comment, Share
from app.models.recommendation import RecommendationImpression, RecommendationClick

log = logging.getLogger(__name__)


class AnalyticsService:
    """Closed-loop analytics, momentum tracking, and editorial opportunity discovery."""

    @staticmethod
    def calculate_demand_supply_matrix(days: int = 30) -> list[dict[str, Any]]:
        """
        Demand vs. Supply Opportunity Matrix (Phase 7 §17.1):
        - Demand: Total interactions (views + likes + comments + saves + shares) over last N days.
        - Volume: Total published content items in same dimension.
        - Opportunity Gap Score: Difference between volume rank and demand rank.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # 1. Category Volume & Demand
        categories = (
            db.session.query(Category)
            .filter(Category.is_active.is_(True))
            .all()
        )

        matrix: list[dict[str, Any]] = []

        for cat in categories:
            # Volume: total published
            volume = (
                db.session.query(func.count(Content.id))
                .filter(
                    Content.category_id == cat.id,
                    Content.is_published.is_(True),
                    Content.is_active.is_(True),
                )
                .scalar() or 0
            )

            # Demand in window
            recent_contents = (
                db.session.query(
                    func.coalesce(func.sum(Content.view_count), 0),
                    func.coalesce(func.sum(Content.like_count), 0),
                    func.coalesce(func.sum(Content.comment_count), 0),
                    func.coalesce(func.sum(Content.save_count), 0),
                    func.coalesce(func.sum(Content.share_count), 0),
                )
                .filter(
                    Content.category_id == cat.id,
                    Content.is_published.is_(True),
                    Content.published_at >= cutoff,
                )
                .first()
            )

            views, likes, comments, saves, shares = recent_contents or (0, 0, 0, 0, 0)
            demand_score = int(views + (likes * 2) + (comments * 3) + (saves * 4) + (shares * 5))

            matrix.append({
                "type": "category",
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "volume": volume,
                "demand": demand_score,
                "views": int(views),
                "engagements": int(likes + comments + saves + shares),
            })

        # Rank by volume and demand
        matrix.sort(key=lambda x: x["volume"], reverse=True)
        for rank, item in enumerate(matrix, start=1):
            item["volume_rank"] = rank

        matrix.sort(key=lambda x: x["demand"], reverse=True)
        for rank, item in enumerate(matrix, start=1):
            item["demand_rank"] = rank
            # Opportunity Gap: higher demand rank than volume rank -> gap > 0
            item["opportunity_gap"] = item["volume_rank"] - item["demand_rank"]
            item["is_priority_opportunity"] = item["opportunity_gap"] >= 3

        # Sort by opportunity gap descending
        matrix.sort(key=lambda x: x["opportunity_gap"], reverse=True)
        return matrix

    @staticmethod
    def calculate_momentum_velocity() -> list[dict[str, Any]]:
        """
        7-Day vs 14-Day Engagement Momentum Velocity (Phase 7 §17.2):
        Growth% = ((Interactions_0-7d - Interactions_8-14d) / max(Interactions_8-14d, 1)) * 100%
        """
        now = datetime.now(timezone.utc)
        d7 = now - timedelta(days=7)
        d14 = now - timedelta(days=14)

        # Query interactions per content in 0-7d vs 8-14d
        views_0_7 = dict(
            db.session.query(View.content_id, func.count(View.id))
            .filter(View.created_at >= d7)
            .group_by(View.content_id)
            .all()
        )
        views_8_14 = dict(
            db.session.query(View.content_id, func.count(View.id))
            .filter(and_(View.created_at >= d14, View.created_at < d7))
            .group_by(View.content_id)
            .all()
        )

        all_content_ids = set(views_0_7.keys()) | set(views_8_14.keys())
        if not all_content_ids:
            return []

        contents = (
            db.session.query(Content)
            .filter(Content.id.in_(all_content_ids), Content.is_published.is_(True))
            .all()
        )

        momentum_results = []
        for c in contents:
            i1 = views_0_7.get(c.id, 0)
            i2 = views_8_14.get(c.id, 0)

            # Growth rate percentage
            growth_pct = round(((i1 - i2) / max(i2, 1)) * 100.0, 2)

            momentum_results.append({
                "content_id": c.id,
                "title": c.title,
                "object_type": c.object_type,
                "interactions_0_7d": i1,
                "interactions_8_14d": i2,
                "growth_pct": growth_pct,
                "is_trending_up": growth_pct > 25.0 and i1 >= 5,
            })

        momentum_results.sort(key=lambda x: x["growth_pct"], reverse=True)
        return momentum_results

    @staticmethod
    def detect_content_traffic_decay() -> list[dict[str, Any]]:
        """
        Content Traffic Decay Detection (Phase 7 §17.3):
        Identifies articles where traffic over days 0–30 is >= 15% lower than days 31–60.
        Schedules 'Update & Refresh' recommendation.
        """
        now = datetime.now(timezone.utc)
        d30 = now - timedelta(days=30)
        d60 = now - timedelta(days=60)

        views_0_30 = dict(
            db.session.query(View.content_id, func.count(View.id))
            .filter(View.created_at >= d30)
            .group_by(View.content_id)
            .all()
        )
        views_31_60 = dict(
            db.session.query(View.content_id, func.count(View.id))
            .filter(and_(View.created_at >= d60, View.created_at < d30))
            .group_by(View.content_id)
            .all()
        )

        decayed_items = []
        for cid, prior_views in views_31_60.items():
            if prior_views < 10:
                continue
            recent_views = views_0_30.get(cid, 0)
            decay_pct = round(((prior_views - recent_views) / prior_views) * 100.0, 2)

            if decay_pct >= 15.0:
                content = db.session.get(Content, cid)
                if content and content.is_published:
                    decayed_items.append({
                        "content_id": cid,
                        "title": content.title,
                        "published_at": content.published_at.isoformat() if content.published_at else None,
                        "views_0_30d": recent_views,
                        "views_31_60d": prior_views,
                        "decay_pct": decay_pct,
                        "action_required": "Update & Refresh (Audit broken embeds, refresh outdated stats & tags)",
                    })

        decayed_items.sort(key=lambda x: x["decay_pct"], reverse=True)
        return decayed_items

    @staticmethod
    def evaluate_closed_loop_feedback() -> list[dict[str, Any]]:
        """
        Closed-Loop Performance Feedback against baseline expectations (Phase 7 §17.4):
        - Strategy Mismatch (Review taxonomy mapping) if CTR_actual < 60% expected
        - Hook/Title Failure (Optimize headline/thumbnail) if high impressions but CTR < 5%
        - Content Mismatch (Improve body readability) if Clicks > 10 but engagement < 2%
        """
        impressions_count = db.session.query(func.count(RecommendationImpression.id)).scalar() or 0
        clicks_count = db.session.query(func.count(RecommendationClick.id)).scalar() or 0

        overall_ctr = round((clicks_count / max(impressions_count, 1)) * 100.0, 2)

        diagnostics = []

        # Evaluate diagnostic rules
        if impressions_count >= 100 and overall_ctr < 5.0:
            diagnostics.append({
                "condition": "Hook / Headline / Thumbnail Failure",
                "severity": "high",
                "recommendation": "Review headline power words, optimize hero thumbnail resolution, and A/B test teaser excerpts.",
                "metric": f"CTR {overall_ctr}% (< 5% threshold)",
            })

        if overall_ctr < 8.0:
            diagnostics.append({
                "condition": "Strategy / Taxonomy Mismatch",
                "severity": "medium",
                "recommendation": "Audit entity associations and category tags to ensure recommendation candidates share high topical overlap.",
                "metric": f"CTR {overall_ctr}% vs expected 10.0%",
            })

        return {
            "total_impressions": impressions_count,
            "total_clicks": clicks_count,
            "overall_ctr_pct": overall_ctr,
            "diagnostics": diagnostics,
        }
