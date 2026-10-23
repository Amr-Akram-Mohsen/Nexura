"""Admin statistics service for dashboard KPI metrics and overview aggregation."""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import func, desc, case

from app.extensions import db
from app.models.content import Content, Article
from app.models.source import Source
from app.models.interaction import View, Comment
from app.models.user import NewsletterSubscriber


class AdminStatsService:
    """Dashboard KPI metrics calculation and recent items overview."""

    @staticmethod
    def get_dashboard_stats() -> dict[str, Any]:
        """Compute KPI metrics and fetch recent contents for the admin dashboard."""
        now = datetime.now(timezone.utc)
        d24h = now - timedelta(hours=24)
        d7d = now - timedelta(days=7)

        # 1. Consolidated Content metrics
        content_stats = db.session.query(
            func.count(Content.id).label("total_contents"),
            func.count(case((Content.object_type == "article", 1))).label("total_articles"),
            func.count(case((Content.object_type == "video", 1))).label("total_videos"),
            func.count(case((Content.is_published.is_(True), 1))).label("published_count"),
        ).first()

        # 2. Consolidated Article pipeline status metrics
        article_stats = db.session.query(
            func.count(case((Article.status == "discovered", 1))).label("discovered_articles"),
            func.count(case((Article.status == "failed", 1))).label("failed_articles"),
        ).first()

        # 3. Consolidated View windowed metrics
        view_stats = db.session.query(
            func.count(case((View.created_at >= d24h, 1))).label("views_24h"),
            func.count(case((View.created_at >= d7d, 1))).label("views_7d"),
        ).first()

        comments_count = db.session.query(func.count(Comment.id)).scalar() or 0
        subscribers_count = (
            db.session.query(func.count(NewsletterSubscriber.id))
            .filter(NewsletterSubscriber.unsubscribed_at.is_(None))
            .scalar()
            or 0
        )
        active_sources = db.session.query(func.count(Source.id)).filter(Source.is_active.is_(True)).scalar() or 0

        recent_items = db.session.query(Content).order_by(desc(Content.id)).limit(8).all()

        kpis = {
            "total_contents": content_stats.total_contents if content_stats else 0,
            "total_articles": content_stats.total_articles if content_stats else 0,
            "total_videos": content_stats.total_videos if content_stats else 0,
            "published_count": content_stats.published_count if content_stats else 0,
            "discovered_articles": article_stats.discovered_articles if article_stats else 0,
            "failed_articles": article_stats.failed_articles if article_stats else 0,
            "views_24h": view_stats.views_24h if view_stats else 0,
            "views_7d": view_stats.views_7d if view_stats else 0,
            "comments_count": comments_count,
            "subscribers_count": subscribers_count,
            "active_sources": active_sources,
        }

        return {"kpis": kpis, "recent_items": recent_items}
