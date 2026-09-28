"""Article repository for article entities, authors, and source syndications."""

from __future__ import annotations
from typing import Sequence
from datetime import datetime, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import selectinload, joinedload

from app.extensions import db
from app.models.article import Article, ArticleSource, article_categories
from app.models.author import Author, article_authors
from app.models.taxonomy import Category, Event


class ArticleRepository:
    """Data access and lifecycle operations for Article records."""

    @staticmethod
    def get_by_id(article_id: int) -> Article | None:
        """Fetch article with authors, sources, categories, and event."""
        return (
            db.session.query(Article)
            .options(
                selectinload(Article.authors),
                selectinload(Article.article_sources).joinedload(ArticleSource.source),
                selectinload(Article.secondary_categories),
                joinedload(Article.event),
            )
            .filter(Article.id == article_id)
            .first()
        )

    @staticmethod
    def get_by_canonical_url(url: str) -> Article | None:
        """Look up existing article by canonical URL."""
        if not url:
            return None
        return db.session.query(Article).filter(Article.canonical_url == url).first()

    @staticmethod
    def get_authors(article_id: int) -> list[Author]:
        """Fetch authors for an article."""
        article = db.session.query(Article).options(selectinload(Article.authors)).filter(Article.id == article_id).first()
        return list(article.authors) if article and article.authors else []

    @staticmethod
    def get_by_source_url(url: str) -> Article | None:
        """Look up article via its syndicated article_sources URL."""
        if not url:
            return None
        article_source = db.session.query(ArticleSource).filter(ArticleSource.url == url).first()
        return article_source.article if article_source else None

    @staticmethod
    def get_needing_enrichment(limit: int = 20) -> list[Article]:
        """Fetch discovered articles ordered by enrichment priority."""
        return db.session.query(Article).filter(Article.status == "discovered").order_by(desc(Article.enrichment_priority), Article.id.asc()).limit(limit).all()

    @staticmethod
    def list_admin(*, status: str | None = None, search: str | None = None, page: int = 1, per_page: int = 30) -> tuple[list[Article], int]:
        """Admin content curation listing with status and search filters."""
        query = db.session.query(Article).options(selectinload(Article.authors), selectinload(Article.article_sources).joinedload(ArticleSource.source))

        if status:
            query = query.filter(Article.status == status)

        if search:
            query = query.filter(Article.title.ilike(f"%{search}%"))

        total = query.with_entities(func.count(Article.id)).scalar() or 0
        articles = query.order_by(desc(Article.id)).offset(max(0, (page - 1) * per_page)).limit(per_page).all()
        return articles, total

    @staticmethod
    def create(
        *,
        title: str,
        description: str | None = None,
        summary: str | None = None,
        body: str | None = None,
        content_text: str | None = None,
        content_html: str | None = None,
        word_count: int | None = None,
        quality_score: float = 0.0,
        enrichment_priority: float = 0.0,
        ingestion_method: str | None = None,
        language: str | None = "en",
        sentiment_score: float | None = None,
        image_url: str | None = None,
        canonical_url: str | None = None,
        status: str = "discovered",
        event_id: int | None = None,
    ) -> Article:
        """Create and persist a new Article instance."""
        article = Article(
            title=title,
            description=description,
            summary=summary,
            body=body,
            content_text=content_text,
            content_html=content_html,
            word_count=word_count,
            quality_score=quality_score,
            enrichment_priority=enrichment_priority,
            ingestion_method=ingestion_method,
            language=language,
            sentiment_score=sentiment_score,
            image_url=image_url,
            canonical_url=canonical_url,
            status=status,
            event_id=event_id,
        )
        db.session.add(article)
        db.session.flush()
        return article

    @staticmethod
    def update_status(article_id: int, new_status: str) -> bool:
        """Update article lifecycle status."""
        valid_statuses = {"discovered", "enriching", "ready", "published", "failed", "archived"}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid article status: {new_status}")

        updated = db.session.query(Article).filter(Article.id == article_id).update({"status": new_status})
        db.session.commit()
        return bool(updated)
