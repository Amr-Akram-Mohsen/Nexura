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
    yield app

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
