"""
Nexura Phase 7 — Admin Ingestions Controller (§18.1, §21)
Handles:
1. Provider health & quota status (NewsAPI, YouTube, Diffbot).
2. Asynchronous manual ingestion runner backed by TaskTracker & daemon threads.
3. Dynamic task status polling API (/api/task/<task_id>).
"""
from __future__ import annotations
import logging
from threading import Thread
from typing import Any

from flask import (
    Blueprint, jsonify, render_template, request, current_app,
)
from sqlalchemy import func, desc

from app.extensions import db
from app.models.source import Source
from app.models.content import Content, Article
from app.ingestion.task_tracker import TaskTracker
from app.routes.admin import admin_required

log = logging.getLogger(__name__)

ingestions_bp = Blueprint("ingestions", __name__)


@ingestions_bp.route("/")
@admin_required
def index():
    """
    Ingestion Health Dashboard (Phase 7 §18.1):
    Displays source status, API quotas, and recent task execution logs.
    """
    sources = (
        db.session.query(Source)
        .order_by(desc(Source.authority_score), Source.name.asc())
        .all()
    )

    recent_tasks = TaskTracker.list_tasks(limit=15)

    # Provider health summary
    providers = [
        {
            "name": "NewsAPI",
            "type": "Article Discovery",
            "status": "Operational" if current_app.config.get("NEWSAPI_KEY") else "Unconfigured",
            "quota": "100 req / day (Developer tier)",
        },
        {
            "name": "YouTube Data API v3",
            "type": "Video Discovery",
            "status": "Operational" if current_app.config.get("YOUTUBE_API_KEY") else "Unconfigured",
            "quota": "10,000 units / day",
        },
        {
            "name": "Diffbot Article API",
            "type": "Deep Extraction & Scraping",
            "status": "Operational" if current_app.config.get("DIFFBOT_TOKEN") else "Unconfigured",
            "quota": "10,000 calls / month",
        },
        {
            "name": "HuggingFace Inference",
            "type": "Sentiment & Spam Scoring",
            "status": "Operational" if current_app.config.get("HUGGINGFACE_API_KEY") else "Mock / Local",
            "quota": "Pay-per-use / Free Inference API",
        },
    ]

    return render_template(
        "admin/ingestions.html",
        sources=sources,
        providers=providers,
        recent_tasks=recent_tasks,
        active_tab="ingestions",
    )


@ingestions_bp.route("/run", methods=["POST"])
@admin_required
def run_ingestion():
    """
    Trigger async ingestion pipeline runner (Phase 7 §21):
    Spawns worker in daemon thread and returns task_id for frontend progress polling.
    """
    source_name = request.form.get("source", "newsapi").strip().lower()
    category = request.form.get("category", "technology")
    limit = request.form.get("limit", 20, type=int)

    # Create background task in TaskTracker
    task_id = TaskTracker.create_task(
        task_name=f"Ingestion: {source_name.capitalize()}",
        source=source_name,
        params={"category": category, "limit": limit},
    )

    # Spawn daemon worker thread with application context
    app = current_app._get_current_object()

    def _worker():
        with app.app_context():
            try:
                TaskTracker.update_progress(task_id, 10, "Initializing pipeline...")
                from app.ingestion.pipeline import IngestionPipeline

                pipeline = IngestionPipeline()
                result = pipeline.run(source_name=source_name, category=category, limit=limit, task_id=task_id)

                TaskTracker.complete_task(
                    task_id,
                    result={
                        "ingested": result.get("ingested", 0),
                        "duplicates": result.get("duplicates", 0),
                        "failed": result.get("failed", 0),
                    },
                )
            except Exception as exc:
                log.exception("Background ingestion task failed: %s", exc)
                TaskTracker.fail_task(task_id, error=str(exc))

    worker_thread = Thread(target=_worker, daemon=True)
    worker_thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": f"Ingestion task for {source_name} started in background.",
    })


@ingestions_bp.route("/api/task/<task_id>")
@admin_required
def get_task_status(task_id: str):
    """Poll live task progress and status JSON (Phase 7 §21)."""
    task = TaskTracker.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)
