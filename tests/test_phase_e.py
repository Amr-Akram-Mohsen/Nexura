import pytest
import os
import shutil
from app import create_app
from app.ingestion import (
    IngestionPipeline, NewsAPIClient, YouTubeClient,
    DiffbotClient, HuggingFaceClient, DuplicateDetector,
    normalize_title, jaccard_similarity, canonicalize_url,
    check_article_quality, TaskTracker
)

@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_task_tracker():
    test_dir = "instance/test_tasks"
    tracker = TaskTracker(state_dir=test_dir)
    
    # Create task
    task_id = tracker.create_task("news_ingestion", {"query": "AI"})
    assert task_id is not None
    
    state = tracker.get_task(task_id)
    assert state["status"] == "pending"
    assert state["source_name"] == "news_ingestion"
    
    # Update task
    tracker.update_status(task_id, status="running", progress=50, message="Halfway")
    updated = tracker.get_task(task_id)
    assert updated["status"] == "running"
    assert updated["progress"] == 50
    assert updated["message"] == "Halfway"
    
    # Complete task
    tracker.update_status(task_id, status="complete", progress=100, message="Done", result={"count": 10})
    completed = tracker.get_task(task_id)
    assert completed["status"] == "complete"
    assert completed["result"]["count"] == 10
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_deduplication_and_normalizer():
    title_a = "Apple Announces iPhone 16 Pro and Max!"
    title_b = "Apple announces iPhone 16 Pro and Max"
    title_c = "Samsung Galaxy S25 Ultra Revealed"
    
    tokens_a = normalize_title(title_a)
    tokens_b = normalize_title(title_b)
    tokens_c = normalize_title(title_c)
    
    # Jaccard matching
    score_ab = jaccard_similarity(tokens_a, tokens_b)
    score_ac = jaccard_similarity(tokens_a, tokens_c)
    
    assert score_ab == 1.0
    assert score_ac < 0.3
    
    detector = DuplicateDetector()
    assert detector.is_duplicate(title_a, [title_b]) is True
    assert detector.is_duplicate(title_c, [title_a, title_b]) is False

def test_quality_gate():
    # Pass: > 250 words and image present
    res_pass = check_article_quality(word_count=350, image_url="https://example.com/photo.jpg")
    assert res_pass.passed is True
    assert res_pass.reason == ""
    
    # Fail: word count <= 250
    res_short = check_article_quality(word_count=180, image_url="https://example.com/photo.jpg")
    assert res_short.passed is False
    assert "word_count" in res_short.reason
    
    # Fail: missing image
    res_no_img = check_article_quality(word_count=400, image_url="")
    assert res_no_img.passed is False
    assert "image_url" in res_no_img.reason

def test_huggingface_sentiment_client():
    client = HuggingFaceClient()
    
    # Positive text
    score_pos, conf_pos, label_pos = client.analyze_sentiment("This breakthrough product is amazing, top quality and I love it!")
    assert score_pos > 0.0
    
    # Negative text
    score_neg, conf_neg, label_neg = client.analyze_sentiment("This terrible device broke immediately and is the worst purchase.")
    assert score_neg < 0.0

def test_youtube_duration_parser():
    from app.ingestion.youtube_client import parse_iso_duration
    
    assert parse_iso_duration("PT15M33S") == 15 * 60 + 33
    assert parse_iso_duration("PT1H2M10S") == 3600 + 2 * 60 + 10
    assert parse_iso_duration("PT45S") == 45
    assert parse_iso_duration("") == 0


# ===========================================================================
# Phase E / Homepage Recommendation & Personalization Tests
# ===========================================================================
from datetime import datetime, timezone
from app.extensions import db, cache
from app.caching import key_home_for_you, invalidate_home_for_you
from app.models.content import Content
from app.models.article import Article
from app.models.taxonomy import Category
from app.models.interaction import View, Save
from app.repositories.user_repo import UserRepository
from app.services.recommendation_service import (
    RecommendationService,
    trending_reason,
    REASON_TRENDING,
)


def _get_or_create_rec_user(email="rec_tester@nexura.tech"):
    user = UserRepository.get_by_email(email)
    if not user:
        user = UserRepository.create(
            email=email,
            password="Password123!",
            name="Recommendation Tester",
            is_admin=False,
            is_verified=True,
        )
    return user


def _get_or_create_rec_category(name="Robotics AI", slug="robotics-ai"):
    cat = db.session.query(Category).filter(Category.slug == slug).first()
    if not cat:
        cat = Category(name=name, slug=slug, is_active=True)
        db.session.add(cat)
        db.session.commit()
    return cat


def _create_rec_content(title, category_id, section_id=1, score=15.0, view_count=200):
    content = db.session.query(Content).filter(Content.title == title).first()
    if not content:
        article = Article(
            title=title,
            summary=f"Summary for {title}",
            status="published",
            word_count=350,
        )
        db.session.add(article)
        db.session.flush()

        content = Content(
            title=title,
            object_type="article",
            object_id=article.id,
            section_id=section_id,
            category_id=category_id,
            score=score,
            view_count=view_count,
            published_at=datetime.now(timezone.utc),
            is_published=True,
            is_active=True,
        )
        db.session.add(content)
        db.session.commit()
    return content


def test_get_trending_items_and_reasons(app):
    """Verify RecommendationService.get_trending_items returns active content with reason attribution."""
    with app.app_context():
        items = RecommendationService.get_trending_items(limit=4)
        assert len(items) > 0
        for item in items:
            assert item.is_active is True
            assert item.is_published is True
            reason = trending_reason(item)
            assert isinstance(reason, str) and len(reason) > 0
            if item.category and item.category.name:
                assert reason == f"Trending in {item.category.name}"
            else:
                assert reason == REASON_TRENDING

        # Verify exclude_ids
        first_id = items[0].id
        excluded_items = RecommendationService.get_trending_items(limit=4, exclude_ids=[first_id])
        assert first_id not in [x.id for x in excluded_items]


def test_personalized_feed_guest_and_cold_start(app):
    """Guests and users without reading history should receive trending fallback with personalized=False."""
    with app.app_context():
        # Guest (user_id=None)
        guest_feed = RecommendationService.get_personalized_feed_with_reasons(user_id=None, limit=6)
        assert guest_feed.personalized is False
        assert len(guest_feed.entries) > 0

        # Cold-start user without any views or saves
        cold_user = _get_or_create_rec_user("cold_start_rec_user@nexura.tech")
        db.session.query(View).filter(View.user_id == cold_user.id).delete()
        db.session.query(Save).filter(Save.user_id == cold_user.id).delete()
        db.session.commit()

        user_feed = RecommendationService.get_personalized_feed_with_reasons(user_id=cold_user.id, limit=6)
        assert user_feed.personalized is False
        assert len(user_feed.entries) > 0


def test_personalized_feed_with_category_interest(app):
    """Users with history should receive items matching their top category with personalized=True and reason badge."""
    with app.app_context():
        user = _get_or_create_rec_user("interest_rec_user@nexura.tech")
        cat = _get_or_create_rec_category("Quantum Systems", "quantum-systems")

        c1 = _create_rec_content("Quantum System Overview", cat.id)
        c2 = _create_rec_content("Quantum System Deep Dive", cat.id)

        # Clear existing views for isolation and add view for c1
        db.session.query(View).filter(View.user_id == user.id).delete()
        db.session.add(View(user_id=user.id, content_id=c1.id))
        db.session.commit()

        feed = RecommendationService.get_personalized_feed_with_reasons(user_id=user.id, limit=6)
        assert feed.personalized is True

        entry_ids = [item.id for item, _ in feed.entries]
        reasons_by_id = {item.id: reason for item, reason in feed.entries}

        # c1 was already seen so it must not be recommended
        assert c1.id not in entry_ids
        # c2 belongs to the viewed category and should be recommended with attribution
        assert c2.id in entry_ids
        assert reasons_by_id[c2.id] == f"Based on your interest in {cat.name}"


def test_homepage_guest_shelf_render(client):
    """Guest visiting homepage sees Trending shelf with sign-in prompt."""
    cache.clear()
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert 'data-home-shelf="trending"' in html
    assert "Trending Now" in html
    assert "What readers are exploring on Nexura right now." in html
    assert "Sign in to personalize" in html


def test_homepage_authenticated_personalized_shelf_render(app, client):
    """Authenticated user with history sees Recommended For You shelf and reason badge."""
    with app.app_context():
        user = _get_or_create_rec_user("home_shelf_rec_user@nexura.tech")
        cat = _get_or_create_rec_category("Robotics Today", "robotics-today")
        c1 = _create_rec_content("Robotics Basics", cat.id)
        c2 = _create_rec_content("Robotics Advanced", cat.id)
        cat_name = cat.name

        db.session.query(View).filter(View.user_id == user.id).delete()
        db.session.add(View(user_id=user.id, content_id=c1.id))
        db.session.commit()
        cache.clear()

    client.post("/auth/login", data={"email": "home_shelf_rec_user@nexura.tech", "password": "Password123!"})

    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert 'data-home-shelf="personalized"' in html
    assert "Recommended For You" in html
    assert "Picked from your reading history and saved stories." in html
    assert f"Based on your interest in {cat_name}" in html
    assert "Sign in to personalize" not in html


def test_homepage_two_tier_caching_and_invalidation(app, client):
    """Verify personalized shelf is cached per-user and invalidated on history mutation."""
    with app.app_context():
        user = _get_or_create_rec_user("cache_shelf_rec_user@nexura.tech")
        user_id = user.id
        cat = _get_or_create_rec_category("Cybersecurity Lab", "cybersecurity-lab")
        c1 = _create_rec_content("Cyber Defense 101", cat.id)
        _create_rec_content("Cyber Defense 201", cat.id)

        db.session.query(View).filter(View.user_id == user.id).delete()
        db.session.add(View(user_id=user.id, content_id=c1.id))
        db.session.commit()
        cache.clear()

    client.post("/auth/login", data={"email": "cache_shelf_rec_user@nexura.tech", "password": "Password123!"})

    # First load caches the user shelf
    res = client.get("/")
    assert res.status_code == 200

    cache_key = key_home_for_you(user_id)
    cached_payload = cache.get(cache_key)
    assert cached_payload is not None
    assert cached_payload["personalized"] is True

    # Invalidate directly
    invalidate_home_for_you(user_id)
    assert cache.get(cache_key) is None

    # Re-cache via page load
    client.get("/")
    assert cache.get(cache_key) is not None

    # Invalidate via history clear endpoint
    res_clear = client.post("/library/history/clear", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res_clear.status_code == 200
    assert cache.get(cache_key) is None

