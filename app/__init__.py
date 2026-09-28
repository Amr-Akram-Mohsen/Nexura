"""Application factory for Nexura."""

from __future__ import annotations
import logging
import os

from flask import Flask

from config import get_config
from app.extensions import db, migrate, login_manager, csrf, limiter, mail, cache, oauth


def create_app(env: str | None = None) -> Flask:
    """Create and configure the Nexura Flask application."""
    app = Flask(__name__, static_folder="../static", template_folder="../templates")

    cfg = get_config(env)
    app.config.from_object(cfg)

    os.makedirs(app.config["TASK_STATE_DIR"], exist_ok=True)

    logging.basicConfig(level=logging.DEBUG if app.config.get("DEBUG") else logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    app.logger.setLevel(logging.DEBUG if app.config.get("DEBUG") else logging.INFO)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)
    cache.init_app(app)
    oauth.init_app(app)

    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    app.google = getattr(oauth, "google", None) or oauth.create_client("google")

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    with app.app_context():
        from app.models import (  # noqa: F401
            taxonomy,
            source,
            content,
            video,
            user,
            interaction,
            recommendation,
            distribution,
            article,
            author,
        )

    _register_blueprints(app)

    from app.services.scheduler_service import init_scheduler
    init_scheduler(app)

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https: blob:; "
            "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com; "
            "connect-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        return response

    from flask import render_template

    @app.errorhandler(400)
    def handle_bad_request(e):
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def handle_forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def handle_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def handle_ratelimit_exceeded(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def handle_server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.shell_context_processor
    def make_shell_context():
        return {"db": db, "app": app}

    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app


def _register_blueprints(app: Flask) -> None:
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.library import library_bp
    from app.routes.interactions import interactions_bp
    from app.routes.seo import seo_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(library_bp)
    app.register_blueprint(interactions_bp)
    app.register_blueprint(seo_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
