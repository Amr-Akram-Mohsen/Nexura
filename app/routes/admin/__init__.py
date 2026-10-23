"""Admin control plane core blueprint, dashboard KPI metrics, and sub-blueprint registry."""

from __future__ import annotations
import functools
import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.services.admin_stats_service import AdminStatsService
from app.utils.audit import log_event

log = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, template_folder="../../templates/admin", static_folder="../../static")


def admin_required(f):
    """Decorator enforcing administrative role access."""

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Administrator login required.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if not getattr(current_user, "is_admin", False):
            log.warning("Unauthorized admin access attempt by user_id=%s email=%s", current_user.id, current_user.email)
            log_event("admin_access_denied", user_id=current_user.id, ip_address=request.remote_addr, details={"path": request.path})
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


@admin_bp.route("/")
@admin_required
def dashboard():
    """Render admin dashboard overview with platform KPI metrics and recent items."""
    data = AdminStatsService.get_dashboard_stats()
    return render_template("admin/dashboard.html", kpis=data["kpis"], recent_items=data["recent_items"], active_tab="dashboard")


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
