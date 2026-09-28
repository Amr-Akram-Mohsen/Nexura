"""Admin ingestions controller for provider health, manual execution, and task polling."""

from __future__ import annotations
import logging
import json
import time
from threading import Thread
from typing import Any

from flask import Blueprint, jsonify, render_template, request, current_app, Response, stream_with_context
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
    """Render ingestion health dashboard with sources, API quotas, and recent tasks."""
    sources = db.session.query(Source).order_by(desc(Source.authority_score), Source.name.asc()).all()

    recent_tasks = TaskTracker.list_tasks(limit=15)

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

    return render_template("admin/ingestions.html", sources=sources, providers=providers, recent_tasks=recent_tasks, active_tab="ingestions")


@ingestions_bp.route("/run", methods=["POST"])
@admin_required
def run_ingestion():
    """Trigger background ingestion pipeline runner and return task ID."""
    source_name = request.form.get("source", "newsapi").strip().lower()
    category = request.form.get("category", "technology")
    limit = request.form.get("limit", 20, type=int)

    task_id = TaskTracker.create_task(task_name=f"Ingestion: {source_name.capitalize()}", source=source_name, params={"category": category, "limit": limit})

    app = current_app._get_current_object()

    def _worker():
        with app.app_context():
            try:
                TaskTracker.update_progress(task_id, 10, "Initializing pipeline...")
                from app.ingestion.pipeline import IngestionPipeline

                pipeline = IngestionPipeline()
                result = pipeline.run(source_name=source_name, category=category, limit=limit, task_id=task_id)

                TaskTracker.complete_task(
                    task_id, result={"ingested": result.get("ingested", 0), "duplicates": result.get("duplicates", 0), "failed": result.get("failed", 0)}
                )
            except Exception as exc:
                log.exception("Background ingestion task failed: %s", exc)
                TaskTracker.fail_task(task_id, error=str(exc))

    worker_thread = Thread(target=_worker, daemon=True)
    worker_thread.start()

    return jsonify({"success": True, "task_id": task_id, "message": f"Ingestion task for {source_name} started in background."})


@ingestions_bp.route("/api/task/<task_id>")
@admin_required
def get_task_status(task_id: str):
    """Return status and progress details for an ingestion task."""
    task = TaskTracker.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)


@ingestions_bp.route("/api/task/<task_id>/stream")
@admin_required
def stream_task_status(task_id: str):
    """Stream live task execution updates via Server-Sent Events (SSE)."""

    def event_stream():
        last_progress = -1
        last_status = None
        max_duration = 300
        start_time = time.time()

        while time.time() - start_time < max_duration:
            state = TaskTracker.get_task(task_id)
            if not state:
                yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                break

            current_progress = state.get("progress", 0)
            current_status = state.get("status")

            if current_progress != last_progress or current_status != last_status:
                last_progress = current_progress
                last_status = current_status
                yield f"data: {json.dumps(state)}\n\n"

            if current_status in ("completed", "complete", "failed"):
                break

            time.sleep(0.5)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

