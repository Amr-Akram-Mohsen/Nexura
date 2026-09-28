"""Automated background scheduler for scheduled ingestion and maintenance tasks."""
from __future__ import annotations
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

def init_scheduler(app: Flask) -> BackgroundScheduler | None:
    """Initialize and start the background scheduler if enabled in configuration."""
    global _scheduler

    if not app.config.get("SCHEDULER_ENABLED"):
        log.info("Scheduler: disabled by configuration.")
        return None

    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)
    interval_hours = app.config.get("SCHEDULER_INTERVAL_HOURS", 6)

    def scheduled_news_ingestion():
        with app.app_context():
            log.info("Scheduler: Running automated news ingestion...")
            try:
                from app.ingestion.pipeline import IngestionPipeline

                pipeline = IngestionPipeline()
                result = pipeline.run_news_ingestion(articles_count=30)
                log.info("Scheduler: News ingestion completed: %s", result)
            except Exception as exc:
                log.error("Scheduler: News ingestion job failed: %s", exc)

    def scheduled_youtube_ingestion():
        with app.app_context():
            log.info("Scheduler: Running automated YouTube ingestion...")
            try:
                from app.ingestion.pipeline import IngestionPipeline

                pipeline = IngestionPipeline()
                result = pipeline.run_youtube_ingestion(query="technology news", max_results=15)
                log.info("Scheduler: YouTube ingestion completed: %s", result)
            except Exception as exc:
                log.error("Scheduler: YouTube ingestion job failed: %s", exc)

    _scheduler.add_job(
        scheduled_news_ingestion,
        "interval",
        hours=interval_hours,
        id="scheduled_news_ingestion",
        replace_existing=True,
    )

    _scheduler.add_job(
        scheduled_youtube_ingestion,
        "interval",
        hours=interval_hours * 2,
        id="scheduled_youtube_ingestion",
        replace_existing=True,
    )

    _scheduler.start()
    log.info("Scheduler: started background jobs (interval=%d hours).", interval_hours)
    return _scheduler

def shutdown_scheduler() -> None:
    """Gracefully shutdown background scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
