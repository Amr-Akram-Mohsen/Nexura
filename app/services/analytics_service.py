"""Analytics, momentum tracking, and editorial opportunity discovery service."""

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
        """Calculate demand vs. supply opportunity matrix across active categories."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        categories = db.session.query(Category).filter(Category.is_active.is_(True)).all()

        matrix: list[dict[str, Any]] = []

        for cat in categories:
            volume = (
                db.session.query(func.count(Content.id))
                .filter(Content.category_id == cat.id, Content.is_published.is_(True), Content.is_active.is_(True))
                .scalar()
                or 0
            )

            recent_contents = (
                db.session.query(
                    func.coalesce(func.sum(Content.view_count), 0),
                    func.coalesce(func.sum(Content.like_count), 0),
                    func.coalesce(func.sum(Content.comment_count), 0),
                    func.coalesce(func.sum(Content.save_count), 0),
                    func.coalesce(func.sum(Content.share_count), 0),
                )
                .filter(Content.category_id == cat.id, Content.is_published.is_(True), Content.published_at >= cutoff)
                .first()
            )

            views, likes, comments, saves, shares = recent_contents or (0, 0, 0, 0, 0)
            demand_score = int(views + (likes * 2) + (comments * 3) + (saves * 4) + (shares * 5))

            matrix.append(
                {
                    "type": "category",
                    "id": cat.id,
                    "name": cat.name,
                    "slug": cat.slug,
                    "volume": volume,
                    "demand": demand_score,
                    "views": int(views),
                    "engagements": int(likes + comments + saves + shares),
                }
            )

        matrix.sort(key=lambda x: x["volume"], reverse=True)
        for rank, item in enumerate(matrix, start=1):
            item["volume_rank"] = rank

        matrix.sort(key=lambda x: x["demand"], reverse=True)
        for rank, item in enumerate(matrix, start=1):
            item["demand_rank"] = rank
            item["opportunity_gap"] = item["volume_rank"] - item["demand_rank"]
            item["is_priority_opportunity"] = item["opportunity_gap"] >= 3

        matrix.sort(key=lambda x: x["opportunity_gap"], reverse=True)
        return matrix

    @staticmethod
    def calculate_momentum_velocity() -> list[dict[str, Any]]:
        """Calculate 7-day vs. 14-day engagement momentum velocity across published content."""
        now = datetime.now(timezone.utc)
        d7 = now - timedelta(days=7)
        d14 = now - timedelta(days=14)

        views_0_7 = dict(db.session.query(View.content_id, func.count(View.id)).filter(View.created_at >= d7).group_by(View.content_id).all())
        views_8_14 = dict(
            db.session.query(View.content_id, func.count(View.id)).filter(and_(View.created_at >= d14, View.created_at < d7)).group_by(View.content_id).all()
        )

        all_content_ids = set(views_0_7.keys()) | set(views_8_14.keys())
        if not all_content_ids:
            return []

        contents = db.session.query(Content).filter(Content.id.in_(all_content_ids), Content.is_published.is_(True)).all()

        momentum_results = []
        for c in contents:
            i1 = views_0_7.get(c.id, 0)
            i2 = views_8_14.get(c.id, 0)
            growth_pct = round(((i1 - i2) / max(i2, 1)) * 100.0, 2)

            momentum_results.append(
                {
                    "content_id": c.id,
                    "title": c.title,
                    "object_type": c.object_type,
                    "interactions_0_7d": i1,
                    "interactions_8_14d": i2,
                    "growth_pct": growth_pct,
                    "is_trending_up": growth_pct > 25.0 and i1 >= 5,
                }
            )

        momentum_results.sort(key=lambda x: x["growth_pct"], reverse=True)
        return momentum_results

    @staticmethod
    def detect_content_traffic_decay() -> list[dict[str, Any]]:
        """Identify content where traffic over days 0-30 dropped by >= 15% vs days 31-60."""
        now = datetime.now(timezone.utc)
        d30 = now - timedelta(days=30)
        d60 = now - timedelta(days=60)

        views_0_30 = dict(db.session.query(View.content_id, func.count(View.id)).filter(View.created_at >= d30).group_by(View.content_id).all())
        views_31_60 = dict(
            db.session.query(View.content_id, func.count(View.id)).filter(and_(View.created_at >= d60, View.created_at < d30)).group_by(View.content_id).all()
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
                    decayed_items.append(
                        {
                            "content_id": cid,
                            "title": content.title,
                            "published_at": content.published_at.isoformat() if content.published_at else None,
                            "views_0_30d": recent_views,
                            "views_31_60d": prior_views,
                            "decay_pct": decay_pct,
                            "action_required": "Update & Refresh (Audit broken embeds, refresh outdated stats & tags)",
                        }
                    )

        decayed_items.sort(key=lambda x: x["decay_pct"], reverse=True)
        return decayed_items

    @staticmethod
    def evaluate_closed_loop_feedback() -> dict[str, Any]:
        """Evaluate recommendation CTR and diagnostic feedback against baselines."""
        impressions_count = db.session.query(func.count(RecommendationImpression.id)).scalar() or 0
        clicks_count = db.session.query(func.count(RecommendationClick.id)).scalar() or 0
        overall_ctr = round((clicks_count / max(impressions_count, 1)) * 100.0, 2)

        diagnostics = []
        if impressions_count >= 100 and overall_ctr < 5.0:
            diagnostics.append(
                {
                    "condition": "Hook / Headline / Thumbnail Failure",
                    "severity": "high",
                    "recommendation": "Review headline power words, optimize hero thumbnail resolution, and A/B test teaser excerpts.",
                    "metric": f"CTR {overall_ctr}% (< 5% threshold)",
                }
            )

        if overall_ctr < 8.0:
            diagnostics.append(
                {
                    "condition": "Strategy / Taxonomy Mismatch",
                    "severity": "medium",
                    "recommendation": "Audit entity associations and category tags to ensure recommendation candidates share high topical overlap.",
                    "metric": f"CTR {overall_ctr}% vs expected 10.0%",
                }
            )

        return {"total_impressions": impressions_count, "total_clicks": clicks_count, "overall_ctr_pct": overall_ctr, "diagnostics": diagnostics}
