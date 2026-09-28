"""
Nexura Phase 7 — Repositories Package
Exposes all data access repositories.
"""

from app.repositories.content_repo import ContentRepository
from app.repositories.article_repo import ArticleRepository
from app.repositories.video_repo import VideoRepository
from app.repositories.taxonomy_repo import TaxonomyRepository
from app.repositories.user_repo import UserRepository
from app.repositories.search_repo import SearchRepository
from app.repositories.analytics_repo import AnalyticsRepository

__all__ = ["ContentRepository", "ArticleRepository", "VideoRepository", "TaxonomyRepository", "UserRepository", "SearchRepository", "AnalyticsRepository"]
