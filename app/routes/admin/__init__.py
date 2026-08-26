"""
Nexura Phase 7 — Admin Control Plane Core & Blueprint (§18)
Defines:
1. @admin_required decorator (rejects unauthenticated/non-admin requests).
2. Root /admin dashboard overview route with platform KPI metrics.
3. Sub-blueprint registration for all 6 operational areas.
"""
from __future__ import annotations
import functools
import logging
from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user
from sqlalchemy import func, desc

from app.extensions import db
from app.models.content import Content, Article
from app.models.video import Video
from app.models.source import Source
from app.models.interaction import View, Comment
from app.models.user import User, NewsletterSubscriber

log = logging.getLogger(__name__)

# Main admin blueprint
admin_bp = Blueprint(
    "admin",
    __name__,
    template_folder="../../templates/admin",
    static_folder="../../static",
)


def admin_required(f):
    """
    Decorator enforcing administrative role access (Phase 7 §14, §18).
    - Unauthenticated requests redirect to login.
    - Authenticated non-admin users receive HTTP 403 Forbidden.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Administrator login required.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if not getattr(current_user, "is_admin", False):
            log.warning(
                "Unauthorized admin access attempt by user_id=%s email=%s",
                current_user.id, current_user.email
            )
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ─── Root Admin Dashboard Overview ───────────────────────────────────────────
@admin_bp.route("/")
@admin_required
def dashboard():
    """
    Admin Dashboard Overview (Phase 7 §18):
    Displays aggregated KPIs: content inventory, traffic, active sources, and health.
    """
    now = datetime.now(timezone.utc)
    d24h = now - timedelta(hours=24)
    d7d = now - timedelta(days=7)

    # 1. Content Inventory Counts
    total_contents = db.session.query(func.count(Content.id)).scalar() or 0
    total_articles = db.session.query(func.count(Content.id)).filter(Content.object_type == "article").scalar() or 0
    total_videos = db.session.query(func.count(Content.id)).filter(Content.object_type == "video").scalar() or 0

    published_count = db.session.query(func.count(Content.id)).filter(Content.is_published.is_(True)).scalar() or 0
    discovered_articles = db.session.query(func.count(Article.id)).filter(Article.status == "discovered").scalar() or 0
    failed_articles = db.session.query(func.count(Article.id)).filter(Article.status == "failed").scalar() or 0

    # 2. Traffic & Interactions
    views_24h = db.session.query(func.count(View.id)).filter(View.created_at >= d24h).scalar() or 0
    views_7d = db.session.query(func.count(View.id)).filter(View.created_at >= d7d).scalar() or 0
    comments_count = db.session.query(func.count(Comment.id)).scalar() or 0
    subscribers_count = db.session.query(func.count(NewsletterSubscriber.id)).filter(NewsletterSubscriber.unsubscribed_at.is_(None)).scalar() or 0

    # 3. Sources
    active_sources = db.session.query(func.count(Source.id)).filter(Source.is_active.is_(True)).scalar() or 0

    # 4. Recent Content Queue
    recent_items = (
        db.session.query(Content)
        .order_by(desc(Content.id))
        .limit(8)
        .all()
    )

    kpis = {
        "total_contents": total_contents,
        "total_articles": total_articles,
        "total_videos": total_videos,
        "published_count": published_count,
        "discovered_articles": discovered_articles,
        "failed_articles": failed_articles,
        "views_24h": views_24h,
        "views_7d": views_7d,
        "comments_count": comments_count,
        "subscribers_count": subscribers_count,
        "active_sources": active_sources,
    }

    return render_template(
        "admin/dashboard.html",
        kpis=kpis,
        recent_items=recent_items,
        active_tab="dashboard",
    )


# ─── Register Operational Sub-Modules ────────────────────────────────────────
from app.routes.admin.ingestions import ingestions_bp
from app.routes.admin.contents import contents_bp
from app.routes.admin.taxonomy import taxonomy_bp
from app.routes.admin.deduplication import deduplication_bp
from app.routes.admin.moderation import moderation_bp
from app.routes.admin.syndication import syndication_bp

admin_bp.register_blueprint(ingestions_bp, url_prefix="/ingestions")
admin_bp.register_blueprint(contents_bp, url_prefix="/contents")
admin_bp.register_blueprint(taxonomy_bp, url_prefix="/taxonomy")
admin_bp.register_blueprint(deduplication_bp, url_prefix="/deduplication")
admin_bp.register_blueprint(moderation_bp, url_prefix="/moderation")
admin_bp.register_blueprint(syndication_bp, url_prefix="/syndication")
