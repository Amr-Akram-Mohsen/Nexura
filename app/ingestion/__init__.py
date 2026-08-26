"""
Nexura Phase 7 — Ingestion Package
Exposes clients, pipeline orchestrators, deduplication, quality gates, and task tracking.
"""
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.newsapi_client import NewsAPIClient
from app.ingestion.youtube_client import YouTubeClient
from app.ingestion.diffbot_client import DiffbotClient
from app.ingestion.huggingface_client import HuggingFaceClient
from app.ingestion.deduplication import DuplicateDetector
from app.ingestion.normalizer import normalize_title, jaccard_similarity, canonicalize_url
from app.ingestion.quality_gate import check_article_quality
from app.ingestion.task_tracker import TaskTracker

__all__ = [
    "IngestionPipeline",
    "NewsAPIClient",
    "YouTubeClient",
    "DiffbotClient",
    "HuggingFaceClient",
    "DuplicateDetector",
    "normalize_title",
    "jaccard_similarity",
    "canonicalize_url",
    "check_article_quality",
    "TaskTracker",
]
