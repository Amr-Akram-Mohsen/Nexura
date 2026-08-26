"""
Nexura Phase 7 — 12-Stage Ingestion Pipeline Orchestrator (§7, §8, §9, §10, §21)
Coordinates discovery, deduplication, full-body extraction, binary quality gates,
entity recognition, sentiment enrichment, taxonomy mapping, master Content creation,
and cascaded cache invalidation.
"""
from __future__ import annotations
import logging
from typing import Any
from datetime import datetime, timezone

from sqlalchemy import func
from app.extensions import db
from app.models.content import Content, Article, ArticleSource, Author, ContentEntity, article_authors
from app.models.video import Video
from app.models.taxonomy import Section, Category, Entity
from app.models.source import Source
from app.repositories.article_repo import ArticleRepository
from app.repositories.video_repo import VideoRepository
from app.repositories.content_repo import ContentRepository
from app.repositories.taxonomy_repo import TaxonomyRepository
from app.ingestion.newsapi_client import NewsAPIClient
from app.ingestion.youtube_client import YouTubeClient
from app.ingestion.diffbot_client import DiffbotClient
from app.ingestion.huggingface_client import HuggingFaceClient
from app.ingestion.deduplication import DuplicateDetector
from app.ingestion.normalizer import canonicalize_url
from app.ingestion.quality_gate import check_article_quality
from app.ingestion.task_tracker import TaskTracker
from app.utils.sanitizer import sanitize_html, sanitize_text
from app.utils.slugify import make_slug
from app.caching import invalidate_content_after_write

log = logging.getLogger(__name__)


class IngestionPipeline:
    """Master multi-source ingestion and enrichment pipeline."""

    def __init__(self, task_tracker: TaskTracker | None = None) -> None:
        self.tracker = task_tracker or TaskTracker()
        self.news_client = NewsAPIClient()
        self.youtube_client = YouTubeClient()
        self.diffbot_client = DiffbotClient()
        self.hf_client = HuggingFaceClient()
        self.dedup_detector = DuplicateDetector()

    # -------------------------------------------------------------------------
    # 1. News Articles Ingestion Pipeline
    # -------------------------------------------------------------------------

    def run_news_ingestion(
        self,
        *,
        keywords: str | None = None,
        category_uri: str | None = None,
        articles_count: int = 25,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute full news ingestion lifecycle.
        Updates task tracker throughout stages.
        """
        if task_id:
            self.tracker.update_status(task_id, status="running", progress=5, message="Fetching raw news items...")

        # Stage 1: Fetch raw feeds
        raw_items = self.news_client.fetch_articles(
            keywords=keywords,
            category_uri=category_uri,
            articles_count=articles_count,
        )

        if not raw_items:
            msg = "No articles returned from upstream API"
            if task_id:
                self.tracker.update_status(task_id, status="complete", progress=100, message=msg, result={"imported": 0})
            return {"imported": 0, "skipped_duplicates": 0, "failed_quality": 0}

        # Pre-load existing titles and canonical URLs for fast batch dedup
        existing_titles = [
            r[0] for r in db.session.query(Content.title)
            .filter(Content.title.isnot(None))
            .order_by(Content.id.desc())
            .limit(2000)
            .all()
        ]

        imported_count = 0
        skipped_dup_count = 0
        failed_quality_count = 0

        total_items = len(raw_items)
        for idx, item in enumerate(raw_items):
            step_progress = 10 + int((idx / total_items) * 85)
            if task_id and idx % 3 == 0:
                self.tracker.update_status(
                    task_id,
                    status="running",
                    progress=step_progress,
                    message=f"Processing article {idx + 1}/{total_items}: {item['title'][:40]}...",
                )

            # Stage 2: URL Canonicalization
            clean_url = canonicalize_url(item["url"])
            if not clean_url:
                continue

            # Check if canonical URL already exists
            if ArticleRepository.get_by_canonical_url(clean_url) or ArticleRepository.get_by_source_url(clean_url):
                skipped_dup_count += 1
                continue

            # Stage 3: Jaccard Deduplication
            if self.dedup_detector.is_duplicate(item["title"], existing_titles):
                skipped_dup_count += 1
                continue

            # Stage 4: Publisher / Source Resolution
            source_domain = item.get("source_domain") or "news.com"
            source = (
                db.session.query(Source)
                .filter(Source.domain == source_domain)
                .first()
            )
            if not source:
                source_slug = make_slug(item.get("source_name") or source_domain)
                source = Source(
                    name=item.get("source_name") or source_domain,
                    slug=source_slug,
                    domain=source_domain,
                    is_active=True,
                    authority_score=50,
                )
                db.session.add(source)
                db.session.flush()

            # Stage 5: Preliminary Article creation (status='discovered')
            article = Article(
                title=sanitize_text(item["title"]),
                description=sanitize_text(item.get("description")),
                summary=sanitize_text(item.get("summary")),
                canonical_url=clean_url,
                image_url=item.get("image_url"),
                language=item.get("language") or "en",
                status="discovered",
                enrichment_priority=float(source.authority_score or 50.0),
                quality_score=0.0,
            )
            db.session.add(article)
            db.session.flush()

            # Create syndicated article_source
            art_source = ArticleSource(
                article_id=article.id,
                source_id=source.id,
                url=clean_url,
                published_at=item.get("published_at"),
            )
            db.session.add(art_source)
            db.session.flush()
            article.primary_source_id = art_source.id

            # Stage 6 & 7: Body & Entity Extraction via Diffbot (if configured) or raw body
            extracted = None
            if self.diffbot_client.token:
                extracted = self.diffbot_client.extract_article(clean_url)

            if extracted:
                article.content_html = sanitize_html(extracted.get("content_html"))
                article.content_text = sanitize_text(extracted.get("content_text"))
                article.word_count = extracted.get("word_count") or 0
                if extracted.get("primary_image_url"):
                    article.image_url = extracted.get("primary_image_url")
            else:
                raw_body = item.get("body") or ""
                article.content_text = sanitize_text(raw_body)
                article.content_html = f"<p>{sanitize_text(raw_body)}</p>" if raw_body else ""
                article.word_count = len(raw_body.split())

            # Stage 8: Binary Quality Gate (Phase 7 §8.2)
            gate = check_article_quality(article.word_count, article.image_url)
            if not gate.passed:
                article.status = "failed"
                failed_quality_count += 1
                db.session.commit()
                continue

            # Stage 9: Sentiment Analysis
            sample_text = article.content_text[:1000] if article.content_text else article.title
            sentiment_score, _, _ = self.hf_client.analyze_sentiment(sample_text)
            article.sentiment_score = sentiment_score

            # Stage 10: Taxonomy Resolution (Section & Category)
            section = db.session.query(Section).filter(Section.is_active.is_(True)).order_by(Section.sort_order.asc()).first()
            section_id = section.id if section else 1

            category = None
            if item.get("raw_categories"):
                cat_name = item["raw_categories"][0]
                cat_slug = make_slug(cat_name)
                category = db.session.query(Category).filter(Category.slug == cat_slug).first()

            # Stage 11: Master Content Aggregator creation
            published_at = item.get("published_at") or datetime.now(timezone.utc)
            content = Content(
                object_type="article",
                object_id=article.id,
                published_at=published_at,
                ingested_at=datetime.now(timezone.utc),
                title=article.title,
                preview_text=article.summary or (article.content_text[:280] if article.content_text else ""),
                search_text=f"{article.title} {article.content_text[:1000] if article.content_text else ''}",
                is_active=True,
                is_published=True,
                section_id=section_id,
                category_id=category.id if category else None,
                source_id=source.id,
                score=50.0 + (source.authority_score * 0.2),
                ingestion_origin="newsapi",
            )
            db.session.add(content)
            db.session.flush()

            # Associate extracted entities
            raw_entities = (extracted.get("entities") if extracted else None) or item.get("raw_concepts", [])
            for ent in raw_entities[:8]:
                ent_name = ent.get("name")
                if not ent_name:
                    continue
                ent_slug = make_slug(ent_name)
                entity_obj = db.session.query(Entity).filter(Entity.slug == ent_slug).first()
                if not entity_obj:
                    entity_obj = Entity(
                        name=ent_name,
                        slug=ent_slug,
                        entity_type=ent.get("type") or "topic",
                        wikidata_id=ent.get("wikidata_id"),
                        wikipedia_url=ent.get("wikipedia_url"),
                    )
                    db.session.add(entity_obj)
                    db.session.flush()

                ce = ContentEntity(
                    content_id=content.id,
                    entity_id=entity_obj.id,
                    relevance_score=float(ent.get("score") or ent.get("relevance_score") or 0.5),
                    origin="diffbot" if extracted else "newsapi",
                )
                db.session.add(ce)

            # Stage 12: Mark Published & Invalidate Cache
            article.status = "published"
            db.session.commit()

            existing_titles.append(article.title)
            imported_count += 1
            invalidate_content_after_write(content.id)

        result_summary = {
            "imported": imported_count,
            "skipped_duplicates": skipped_dup_count,
            "failed_quality": failed_quality_count,
            "total_evaluated": total_items,
        }

        if task_id:
            msg = f"News Ingestion complete: {imported_count} imported, {skipped_dup_count} duplicates skipped."
            self.tracker.update_status(task_id, status="complete", progress=100, message=msg, result=result_summary)

        return result_summary

    # -------------------------------------------------------------------------
    # 2. YouTube Videos Ingestion Pipeline
    # -------------------------------------------------------------------------

    def run_youtube_ingestion(
        self,
        *,
        query: str,
        max_results: int = 20,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute YouTube video ingestion:
        Searches videos, dedups by external_id, saves Video record, fetches top comments,
        creates master Content record, and invalidates cache.
        """
        if task_id:
            self.tracker.update_status(task_id, status="running", progress=10, message=f"Searching YouTube for '{query}'...")

        videos_data = self.youtube_client.search_videos(query, max_results=max_results)
        if not videos_data:
            msg = "No videos returned from YouTube API"
            if task_id:
                self.tracker.update_status(task_id, status="complete", progress=100, message=msg, result={"imported": 0})
            return {"imported": 0, "skipped_duplicates": 0}

        imported_count = 0
        skipped_dup_count = 0
        total_items = len(videos_data)

        section = db.session.query(Section).filter(Section.is_active.is_(True)).order_by(Section.sort_order.asc()).first()
        section_id = section.id if section else 1

        for idx, item in enumerate(videos_data):
            step_progress = 15 + int((idx / total_items) * 80)
            if task_id and idx % 2 == 0:
                self.tracker.update_status(
                    task_id,
                    status="running",
                    progress=step_progress,
                    message=f"Saving video {idx + 1}/{total_items}: {item['title'][:40]}...",
                )

            # Deduplication by YouTube external_id
            if VideoRepository.get_by_external_id(item["external_id"]):
                skipped_dup_count += 1
                continue

            # Create Video record
            video = Video(
                external_id=item["external_id"],
                platform="youtube",
                title=sanitize_text(item["title"]),
                description=sanitize_text(item.get("description")),
                thumbnail_url=item.get("thumbnail_url"),
                channel_name=item.get("channel_name"),
                channel_id=item.get("channel_id"),
                url=item.get("url"),
                creator=item.get("creator"),
                duration_seconds=item.get("duration_seconds"),
                view_count=item.get("view_count", 0),
                like_count=item.get("like_count", 0),
                comments_count=item.get("comments_count", 0),
                published_at=item.get("published_at"),
                platform_metadata=item.get("platform_metadata"),
            )
            db.session.add(video)
            db.session.flush()

            # Fetch top YouTube comments
            comments = self.youtube_client.fetch_top_comments(video.external_id, max_results=10)
            for c in comments:
                VideoRepository.upsert_comment(
                    video_id=video.id,
                    external_id=c["external_id"],
                    author_name=c.get("author_name"),
                    author_channel_id=c.get("author_channel_id"),
                    text=c["text"],
                    like_count=c.get("like_count", 0),
                    reply_count=c.get("reply_count", 0),
                    published_at=c.get("published_at"),
                )

            # Master Content record
            content = Content(
                object_type="video",
                object_id=video.id,
                published_at=video.published_at or datetime.now(timezone.utc),
                ingested_at=datetime.now(timezone.utc),
                title=video.title,
                preview_text=video.description[:280] if video.description else "",
                search_text=f"{video.title} {video.channel_name or ''} {video.description[:500] if video.description else ''}",
                is_active=True,
                is_published=True,
                section_id=section_id,
                score=40.0 + min(float(video.view_count or 0) / 50000.0, 50.0),
                ingestion_origin="youtube",
            )
            db.session.add(content)
            db.session.commit()

            imported_count += 1
            invalidate_content_after_write(content.id)

        result_summary = {
            "imported": imported_count,
            "skipped_duplicates": skipped_dup_count,
            "total_evaluated": total_items,
        }

        if task_id:
            msg = f"YouTube Ingestion complete: {imported_count} videos imported, {skipped_dup_count} duplicates skipped."
            self.tracker.update_status(task_id, status="complete", progress=100, message=msg, result=result_summary)

        return result_summary
