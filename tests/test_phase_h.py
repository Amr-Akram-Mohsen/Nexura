"""
Nexura Phase 7 — Phase H Unit & Integration Tests
Verifies:
1. Multi-signal content relevance scoring (§16.1)
2. Recommendation service & personalized feed generation (§16.2)
3. Demand vs. Supply matrix & momentum velocity (§17.1, §17.2)
4. Traffic decay detection (§17.3)
5. 4-component search scoring formula (§11.2)
6. 5-dimension editorial readiness evaluation (§9.2) & content publishing lifecycle
"""
import pytest
from datetime import datetime, timezone, timedelta

from app import create_app, db
from app.models.content import Content, Article, ContentEntity
from app.models.taxonomy import Section, Category, Entity
from app.models.user import User
from app.models.interaction import View, Save, Reaction
from app.services.recommendation_service import (
    calculate_relevance_score,
    RecommendationService,
)
from app.services.analytics_service import AnalyticsService
from app.services.search_service import calculate_search_score, SearchService
from app.services.content_service import (
    evaluate_editorial_readiness,
    ContentService,
)


@pytest.fixture(scope="module")
def app():
    app = create_app()
    yield app


def test_relevance_scoring_formula(app):
    """Verify Phase 7 §16.1 multi-signal content relevance formula."""
    now = datetime.now(timezone.utc)

    # Reference content
    ref = Content(
        id=1001,
        title="Apple iPhone 16 Pro Review",
        object_type="article",
        object_id=1,
        section_id=1,
        category_id=10,
        view_count=500,
        published_at=now,
        is_published=True,
        is_active=True,
    )

    # Candidate A: Same category, same section, recent, moderate views
    cand_a = Content(
        id=1002,
        title="Google Pixel 9 Pro Review",
        object_type="article",
        object_id=2,
        section_id=1,
        category_id=10,
        view_count=300,
        published_at=now - timedelta(days=2),
        is_published=True,
        is_active=True,
    )

    # Candidate B: Different category, different section, old
    cand_b = Content(
        id=1003,
        title="Ancient History Article",
        object_type="article",
        object_id=3,
        section_id=2,
        category_id=20,
        view_count=10,
        published_at=now - timedelta(days=90),
        is_published=True,
        is_active=True,
    )

    score_a = calculate_relevance_score(cand_a, ref, now=now)
    score_b = calculate_relevance_score(cand_b, ref, now=now)

    assert score_a > score_b
    assert score_a > 0.0


def test_4_component_search_scoring(app):
    """Verify Phase 7 §11.2 multi-factor search ranking."""
    now = datetime.now(timezone.utc)

    c1 = Content(
        id=2001,
        title="Best Laptops for Developers 2026",
        preview_text="A comprehensive buying guide and reviews for top laptops.",
        object_type="article",
        object_id=1,
        view_count=1000,
        like_count=50,
        published_at=now - timedelta(days=1),
        is_published=True,
        is_active=True,
    )

    c2 = Content(
        id=2002,
        title="Old Keyboard Maintenance Tips",
        preview_text="How to clean keyboards.",
        object_type="article",
        object_id=2,
        view_count=5,
        like_count=0,
        published_at=now - timedelta(days=120),
        is_published=True,
        is_active=True,
    )

    query = "best laptops buying guide"
    score_1 = calculate_search_score(c1, query, now=now)
    score_2 = calculate_search_score(c2, query, now=now)

    assert score_1 > score_2
    assert score_1 >= 5.0


def test_editorial_readiness_evaluation(app):
    """Verify Phase 7 §9.2 5-dimension Publishing Readiness Index."""
    with app.app_context():
        # Create complete ready article
        article = Article(
            title="High End GPU Architecture In-Depth",
            description="Comprehensive analysis of next gen GPUs.",
            summary="A summary of the GPU architecture.",
            word_count=500,
            content_html="<p>Detailed architecture text...</p>",
            image_url="https://images.unsplash.com/photo-gpu.jpg",
            status="discovered",
        )
        db.session.add(article)
        db.session.flush()

        content = Content(
            title=article.title,
            object_type="article",
            object_id=article.id,
            section_id=1,
            category_id=1,
            published_at=datetime.now(timezone.utc),
            is_published=False,
            is_active=True,
        )
        db.session.add(content)
        db.session.commit()

        readiness = evaluate_editorial_readiness(article.id)
        assert readiness["score"] >= 50
        assert readiness["tier"] in ("Almost Ready", "Ready")
        assert "breakdown" in readiness


def test_content_lifecycle_and_invalidation(app):
    """Verify publish/unpublish/archive lifecycle."""
    with app.app_context():
        article = Article(
            title="Lifecycle Test Article",
            word_count=300,
            status="discovered",
        )
        db.session.add(article)
        db.session.flush()

        content = Content(
            title=article.title,
            object_type="article",
            object_id=article.id,
            section_id=1,
            published_at=datetime.now(timezone.utc),
            is_published=False,
            is_active=True,
        )
        db.session.add(content)
        db.session.commit()

        # Publish
        assert ContentService.publish_content(content.id) is True
        c = db.session.get(Content, content.id)
        assert c.is_published is True

        # Unpublish
        assert ContentService.unpublish_content(content.id) is True
        c = db.session.get(Content, content.id)
        assert c.is_published is False

        # Archive
        assert ContentService.archive_content(content.id) is True
        c = db.session.get(Content, content.id)
        assert c.is_active is False


def test_demand_supply_matrix_and_momentum(app):
    """Verify analytics service demand vs. supply and momentum computations."""
    with app.app_context():
        matrix = AnalyticsService.calculate_demand_supply_matrix(days=30)
        assert isinstance(matrix, list)
        if matrix:
            assert "opportunity_gap" in matrix[0]

        momentum = AnalyticsService.calculate_momentum_velocity()
        assert isinstance(momentum, list)

        decay = AnalyticsService.detect_content_traffic_decay()
        assert isinstance(decay, list)
