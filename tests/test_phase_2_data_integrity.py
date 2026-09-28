"""
Tests for Nexura Phase 2 Data Integrity Fixes:
FIX-05: Ingestion pipeline transaction savepoints (prevent orphaned records on failure)
FIX-06: Deduplication cluster resolver (soft-delete cascade & per-content cache invalidation)
"""
from __future__ import annotations
import secrets
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import create_app, db
from app.models.content import Content, ContentEntity
from app.models.article import Article, ArticleSource
from app.models.video import Video, VideoComment
from app.models.taxonomy import Section
from app.models.source import Source
from app.repositories.user_repo import UserRepository
from app.ingestion.pipeline import IngestionPipeline


@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["MAIL_ENABLED"] = False
    yield app


def _clean_test_db():
    try:
        c_ids = [c[0] for c in db.session.query(Content.id).filter(Content.title.like("Phase 2 Test%")).all()]
        if c_ids:
            db.session.query(ContentEntity).filter(ContentEntity.content_id.in_(c_ids)).delete(synchronize_session=False)
            db.session.query(Content).filter(Content.id.in_(c_ids)).delete(synchronize_session=False)

        arts = db.session.query(Article).filter(Article.title.like("Phase 2 Test%")).all()
        for a in arts:
            a.primary_source_id = None
        db.session.flush()

        art_ids = [a.id for a in arts]
        if art_ids:
            db.session.query(ArticleSource).filter(ArticleSource.article_id.in_(art_ids)).delete(synchronize_session=False)
            db.session.query(Article).filter(Article.id.in_(art_ids)).delete(synchronize_session=False)

        vid_ids = [v[0] for v in db.session.query(Video.id).filter(Video.title.like("Phase 2 Test%")).all()]
        if vid_ids:
            db.session.query(VideoComment).filter(VideoComment.video_id.in_(vid_ids)).delete(synchronize_session=False)
            db.session.query(Video).filter(Video.id.in_(vid_ids)).delete(synchronize_session=False)

        db.session.commit()
    except Exception:
        db.session.rollback()


@pytest.fixture(autouse=True)
def cleanup_data(app):
    with app.app_context():
        _clean_test_db()
    yield
    with app.app_context():
        _clean_test_db()


def test_fix05_news_ingestion_savepoint_isolation(app):
    """Verify that a mid-article failure rolls back only that article's savepoint, allowing subsequent articles to succeed."""
    pipeline = IngestionPipeline()
    uid = secrets.token_hex(4)

    raw_items = [
        {
            "title": f"Phase 2 Test Article Failing Midstream {uid}",
            "url": f"https://example.com/phase2-failing-{uid}",
            "description": "Fails during sentiment or entity creation",
            "summary": "Fails during processing",
            "source_domain": "phase2fail.com",
            "source_name": "Phase2 Fail Source",
            "image_url": "https://example.com/hero1.jpg",
            "published_at": datetime.now(timezone.utc),
            "body": "A long article body text that easily satisfies the 250 word requirement to pass the quality check. " * 30,
        },
        {
            "title": f"Phase 2 Test Article Successful {uid}",
            "url": f"https://example.com/phase2-success-{uid}",
            "description": "Succeeds completely",
            "summary": "Succeeds completely",
            "source_domain": "phase2pass.com",
            "source_name": "Phase2 Pass Source",
            "image_url": "https://example.com/hero2.jpg",
            "published_at": datetime.now(timezone.utc),
            "body": "A long article body text that easily satisfies the 250 word requirement to pass the quality check. " * 30,
        },
    ]

    with app.app_context():
        # Ensure at least one active section exists
        if not db.session.query(Section).filter(Section.is_active.is_(True)).first():
            db.session.add(Section(name="Tech", slug="tech", is_active=True, sort_order=1))
            db.session.commit()

        with patch.object(pipeline.news_client, "fetch_articles", return_value=raw_items), \
             patch.object(pipeline.diffbot_client, "extract_article", return_value=None):

            # Simulate HF client raising an exception ONLY on the first article
            call_count = 0

            def mock_sentiment(text):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("Simulated HF API connection timeout!")
                return 0.75, "positive", 0.95

            with patch.object(pipeline.hf_client, "analyze_sentiment", side_effect=mock_sentiment):
                res = pipeline.run_news_ingestion()

                assert res["imported"] == 1
                assert res["failed_quality"] == 1

                # Verify failing article was rolled back and NOT left as orphaned discovered article
                failing_art = db.session.query(Article).filter(Article.title == f"Phase 2 Test Article Failing Midstream {uid}").first()
                assert failing_art is None

                # Verify successful article was committed with Content
                success_art = db.session.query(Article).filter(Article.title == f"Phase 2 Test Article Successful {uid}").first()
                assert success_art is not None
                assert success_art.status == "published"

                success_content = db.session.query(Content).filter(Content.title == f"Phase 2 Test Article Successful {uid}").first()
                assert success_content is not None
                assert success_content.object_id == success_art.id


def test_fix05_youtube_ingestion_savepoint_isolation(app):
    """Verify that a video failure during comments upsert rolls back only that video savepoint."""
    pipeline = IngestionPipeline()
    uid = secrets.token_hex(4)

    videos_data = [
        {
            "external_id": f"phase2_yt_fail_{uid}",
            "title": f"Phase 2 Test Video Failing {uid}",
            "description": "Fails during comments",
            "thumbnail_url": "https://example.com/thumb1.jpg",
            "channel_name": "Fail Channel",
            "channel_id": "ch_fail",
            "url": f"https://youtube.com/watch?v=phase2_yt_fail_{uid}",
            "published_at": datetime.now(timezone.utc),
        },
        {
            "external_id": f"phase2_yt_pass_{uid}",
            "title": f"Phase 2 Test Video Success {uid}",
            "description": "Succeeds completely",
            "thumbnail_url": "https://example.com/thumb2.jpg",
            "channel_name": "Pass Channel",
            "channel_id": "ch_pass",
            "url": f"https://youtube.com/watch?v=phase2_yt_pass_{uid}",
            "published_at": datetime.now(timezone.utc),
        },
    ]

    with app.app_context():
        with patch.object(pipeline.youtube_client, "search_videos", return_value=videos_data):
            # Simulate failure on first video's comment fetch
            yt_call = 0

            def mock_comments(ext_id, max_results=10):
                nonlocal yt_call
                yt_call += 1
                if yt_call == 1:
                    raise RuntimeError("Simulated YouTube Comments API Quota Error")
                return []

            with patch.object(pipeline.youtube_client, "fetch_top_comments", side_effect=mock_comments):
                res = pipeline.run_youtube_ingestion(query="test")
                assert res["imported"] == 1

                # Verify failed video was rolled back cleanly
                fail_vid = db.session.query(Video).filter(Video.external_id == f"phase2_yt_fail_{uid}").first()
                assert fail_vid is None

                # Verify successful video was persisted with Content
                pass_vid = db.session.query(Video).filter(Video.external_id == f"phase2_yt_pass_{uid}").first()
                assert pass_vid is not None

                pass_content = db.session.query(Content).filter(Content.title == f"Phase 2 Test Video Success {uid}").first()
                assert pass_content is not None
                assert pass_content.object_id == pass_vid.id


def test_fix06_deduplication_cluster_resolver(app):
    """Verify FIX-06: resolve_cluster creates ArticleSource without is_primary error, sets archived, and invalidates content caches."""
    client = app.test_client()
    uid = secrets.token_hex(4)

    with app.app_context():
        # Setup admin user
        admin = UserRepository.get_by_email("phase2_admin@nexura.tech")
        if not admin:
            admin = UserRepository.create(
                email="phase2_admin@nexura.tech",
                password="Password123!",
                name="Phase 2 Admin",
                is_admin=True,
                is_verified=True,
            )
        else:
            admin.is_admin = True
            admin.is_verified = True
            UserRepository.update_password(admin, "Password123!")

        # Setup source
        source = db.session.query(Source).first()
        if not source:
            source = Source(name="Test Source", slug="test-source", domain="test.com", is_active=True, authority_score=50)
            db.session.add(source)
            db.session.commit()
        source_id = source.id

        # Create canonical article & content
        canonical_art = Article(
            title=f"Phase 2 Test Canonical Story {uid}",
            canonical_url=f"https://test.com/canonical-story-{uid}",
            status="published",
            word_count=500,
        )
        db.session.add(canonical_art)
        db.session.flush()

        canonical_content = Content(
            object_type="article",
            object_id=canonical_art.id,
            title=f"Phase 2 Test Canonical Story {uid}",
            is_active=True,
            is_published=True,
            source_id=source_id,
            section_id=1,
            published_at=datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
        )
        db.session.add(canonical_content)

        # Create duplicate article & content
        dup_art = Article(
            title=f"Phase 2 Test Duplicate Story {uid}",
            canonical_url=f"https://test.com/dup-story-url-{uid}",
            status="published",
            word_count=450,
        )
        db.session.add(dup_art)
        db.session.flush()

        dup_content = Content(
            object_type="article",
            object_id=dup_art.id,
            title=f"Phase 2 Test Duplicate Story {uid}",
            is_active=True,
            is_published=True,
            source_id=source_id,
            section_id=1,
            published_at=datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
        )
        db.session.add(dup_content)
        db.session.commit()

        canonical_id = canonical_art.id
        dup_id = dup_art.id
        canonical_cid = canonical_content.id
        dup_cid = dup_content.id

    # Log in as admin
    client.post("/auth/login", data={"email": "phase2_admin@nexura.tech", "password": "Password123!"})

    with patch("app.routes.admin.deduplication.invalidate_content_after_write") as mock_invalidate:
        res = client.post("/admin/deduplication/resolve", data={
            "canonical_id": str(canonical_id),
            "duplicate_ids": [str(dup_id)],
        })

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["resolved_count"] == 1

        # Check that invalidate was called for both duplicate content ID and canonical content ID
        invalidated_ids = [call.args[0] for call in mock_invalidate.call_args_list if call.args]
        assert dup_cid in invalidated_ids
        assert canonical_cid in invalidated_ids

    # Verify database state
    with app.app_context():
        # Duplicate article should be archived
        refreshed_dup = db.session.get(Article, dup_id)
        assert refreshed_dup.status == "archived"

        refreshed_dup_content = db.session.get(Content, dup_cid)
        assert refreshed_dup_content.is_published is False
        assert refreshed_dup_content.is_active is False

        # ArticleSource should be linked to canonical
        linked_src = db.session.query(ArticleSource).filter(
            ArticleSource.article_id == canonical_id,
            ArticleSource.url == f"https://test.com/dup-story-url-{uid}",
        ).first()
        assert linked_src is not None
        assert linked_src.source_id == source_id
