"""
Tests for Nexura Article & Video Consumption Experience:
- Article and Video detail page rendering and Schema.org structured data
- Breadcrumb navigation and BreadcrumbList hierarchy
- Multi-signal recommendation ranking and explanatory reason attribution
- Zero forbidden inline styles on article and video templates
- Canonical slug redirection and share interactions
"""
from __future__ import annotations
import re
import pytest
from app import create_app, db
from app.models.content import Content
from app.models.article import Article
from app.models.video import Video
from app.services.recommendation_service import RecommendationService


@pytest.fixture(scope="module")
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def test_article_page_breadcrumbs_and_schema(app, client):
    """Article detail page renders Schema.org NewsArticle and 4-tier breadcrumbs."""
    with app.app_context():
        content = (
            db.session.query(Content)
            .filter(Content.object_type == "article", Content.is_published.is_(True), Content.is_active.is_(True))
            .first()
        )
        assert content is not None, "At least one published article required for test"
        slug_id = content.slug_id
        sec_name = content.section.name if content.section else None
        cat_name = content.category.name if content.category else None

    res = client.get(f"/article/{slug_id}")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Breadcrumb verification
    assert 'aria-label="Breadcrumb"' in html
    assert 'itemtype="https://schema.org/BreadcrumbList"' in html
    assert 'Home' in html
    if sec_name:
        assert sec_name in html
    if cat_name:
        import html as html_lib
        assert html_lib.escape(cat_name) in html or cat_name in html

    # Schema.org NewsArticle structured data
    assert 'itemtype="https://schema.org/NewsArticle"' in html
    assert '"@type": "NewsArticle"' in html

    # Content with sidebar layout
    assert 'class="content-with-sidebar"' in html
    assert 'class="sidebar"' in html


def test_video_page_breadcrumbs_and_facade(app, client):
    """Video detail page renders VideoObject, breadcrumbs, video facade, and share button."""
    with app.app_context():
        content = (
            db.session.query(Content)
            .filter(Content.object_type == "video", Content.is_published.is_(True), Content.is_active.is_(True))
            .first()
        )
        assert content is not None, "At least one published video required for test"
        slug_id = content.slug_id

    res = client.get(f"/video/{slug_id}")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Breadcrumb verification
    assert 'aria-label="Breadcrumb"' in html
    assert 'itemtype="https://schema.org/BreadcrumbList"' in html
    assert 'Home' in html

    # Video facade & Schema.org verification
    assert 'itemtype="https://schema.org/VideoObject"' in html
    assert 'class="video-facade"' in html
    assert 'data-video-id="' in html
    assert 'class="video-page-header"' in html

    # Share dialog target ID
    assert 'id="video-share-copy-link-btn"' in html


def test_reading_experience_zero_forbidden_inline_styles(app, client):
    """Confirm zero legacy inline styles in article and video templates."""
    with app.app_context():
        art_content = (
            db.session.query(Content)
            .filter(Content.object_type == "article", Content.is_published.is_(True), Content.is_active.is_(True))
            .first()
        )
        vid_content = (
            db.session.query(Content)
            .filter(Content.object_type == "video", Content.is_published.is_(True), Content.is_active.is_(True))
            .first()
        )
        assert art_content is not None
        assert vid_content is not None
        art_slug_id = art_content.slug_id
        vid_slug_id = vid_content.slug_id

    forbidden_style_patterns = [
        "padding-top:",
        "margin-top:",
        "margin-bottom:",
        "display:flex",
        "display:grid",
        "grid-template",
        "font-size:",
        "font-weight:",
        "line-height:",
        "border-radius:",
    ]

    # 1. Article Page: zero forbidden layout/typography style attributes
    art_res = client.get(f"/article/{art_slug_id}")
    art_html = art_res.get_data(as_text=True)
    for pat in forbidden_style_patterns:
        assert pat not in art_html, f"Forbidden inline style '{pat}' found in article template"

    # 2. Video Page: zero forbidden layout/typography style attributes
    vid_res = client.get(f"/video/{vid_slug_id}")
    vid_html = vid_res.get_data(as_text=True)
    for pat in forbidden_style_patterns:
        assert pat not in vid_html, f"Forbidden inline style '{pat}' found in video template"

    # Verify only modern CSS custom variable bindings exist on video elements
    vid_style_matches = re.findall(r'style="([^"]*)"', vid_html)
    for style_val in vid_style_matches:
        assert any(
            allowed in style_val for allowed in ("--ambient-bg:", "--avatar-gradient:", "display:none")
        ), f"Unexpected inline style found in video: {style_val}"


def test_related_content_recommendations_and_attribution(app, client):
    """Verify related content recommendations return multi-signal attribution reasons."""
    with app.app_context():
        art_content = (
            db.session.query(Content)
            .filter(Content.object_type == "article", Content.is_published.is_(True), Content.is_active.is_(True))
            .first()
        )
        assert art_content is not None

        # Test service layer
        related_pairs = RecommendationService.get_related_recommendations_with_reasons(art_content.id, limit=6)
        if related_pairs:
            for item, reason in related_pairs:
                assert item is not None
                assert reason is None or any(
                    reason.startswith(prefix) for prefix in ("Topic:", "Brand:", "Category:", "Section:", "Related story")
                )

    # Test template rendering
    res = client.get(f"/article/{art_content.slug_id}")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Related section classes
    if related_pairs:
        assert 'class="related-section"' in html
        assert 'class="related-section__grid"' in html
        assert 'class="related-articles-list"' in html


def test_canonical_slug_redirect(app, client):
    """Accessing /article/{id} redirects 301 to the canonical slug URL."""
    with app.app_context():
        art_content = (
            db.session.query(Content)
            .filter(Content.object_type == "article", Content.is_published.is_(True), Content.is_active.is_(True))
            .first()
        )
        assert art_content is not None
        cid = art_content.id
        expected_slug = art_content.slug_id

    res = client.get(f"/article/{cid}")
    if art_content.slug:
        assert res.status_code == 301
        assert f"/article/{expected_slug}" in res.headers["Location"]
    else:
        assert res.status_code == 200
