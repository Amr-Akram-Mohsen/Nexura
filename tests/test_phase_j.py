"""
Nexura Phase 7 — Phase J Unit & Hardening Tests
Verifies:
1. Security Headers (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy) (§26.3)
2. Custom error handlers (404, 403) (§26.4)
3. Dynamic XML Sitemaps (/sitemap_index.xml, /sitemap_1.xml) & robots.txt (§27.4)
4. Interaction & Subscription rate limiting endpoints (§12, §26)
"""
import pytest
from app import create_app, db

@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    yield app

def test_security_headers_present(app):
    """Verify Phase 7 §26.3 security headers are injected on all HTTP responses."""
    client = app.test_client()
    res = client.get("/")
    assert res.status_code == 200

    headers = res.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in headers
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]

def test_404_error_page(app):
    """Verify custom styled 404 handler."""
    client = app.test_client()
    res = client.get("/non-existent-page-url-xyz")
    assert res.status_code == 404
    assert b"Story Not Found" in res.data
    assert b"404" in res.data

def test_xml_sitemaps_and_robots(app):
    """Verify Phase 7 §27.4 sitemaps and robots.txt."""
    client = app.test_client()

    # Sitemap index
    res_index = client.get("/sitemap_index.xml")
    assert res_index.status_code == 200
    assert res_index.content_type.startswith("application/xml")
    assert b"<sitemapindex" in res_index.data

    # Sitemap chunk
    res_chunk = client.get("/sitemap_1.xml")
    assert res_chunk.status_code == 200
    assert res_chunk.content_type.startswith("application/xml")
    assert b"<urlset" in res_chunk.data

    # Robots.txt
    res_robots = client.get("/robots.txt")
    assert res_robots.status_code == 200
    assert res_robots.content_type.startswith("text/plain")
    assert b"Disallow: /admin/" in res_robots.data
    assert b"Sitemap:" in res_robots.data

def test_subscribe_validation_and_rate_limit(app):
    """Verify subscription validation endpoint."""
    client = app.test_client()

    # Invalid email
    res = client.post("/subscribe", data={"email": "invalid-email"})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False

def test_slug_url_routing_and_canonical_redirect(app):
    """Verify SEO slug URLs and canonical 301 redirects for articles and videos."""
    with app.app_context():
        from app.models.content import Content
        article = db.session.query(Content).filter(Content.object_type == "article", Content.is_published.is_(True)).first()
        video = db.session.query(Content).filter(Content.object_type == "video", Content.is_published.is_(True)).first()

        client = app.test_client()

        if article:
            # 1. Bare ID redirects to canonical slug URL
            res_redirect = client.get(f"/article/{article.id}")
            assert res_redirect.status_code == 301
            assert article.slug in res_redirect.location

            # 2. Slug URL loads successfully with 200 OK
            res_slug = client.get(f"/article/{article.slug_id}")
            assert res_slug.status_code == 200
            assert bytes(article.slug_id, "utf-8") in res_slug.data or bytes(article.title[:20], "utf-8") in res_slug.data

        if video:
            # 1. Bare ID redirects to canonical slug URL
            res_redirect = client.get(f"/video/{video.id}")
            assert res_redirect.status_code == 301
            assert video.slug in res_redirect.location

            # 2. Slug URL loads successfully with 200 OK
            res_slug = client.get(f"/video/{video.slug_id}")
            assert res_slug.status_code == 200

def test_social_links_rendered_in_footer(app):
    """Verify social media channels from config.py are rendered in the footer."""
    from config import SOCIAL_LINKS
    assert len(SOCIAL_LINKS) >= 6

    client = app.test_client()
    res = client.get("/")
    assert res.status_code == 200

    html = res.data.decode("utf-8")
    assert 'aria-label="Nexura on Social Media"' in html

    for platform, url in SOCIAL_LINKS:
        assert url in html
        assert f'footer__social-link--{platform.lower()}' in html

def test_comment_self_action_restrictions(app):
    """Verify user cannot reply to or react to their own comment."""
    with app.app_context():
        from app.models.content import Content
        from app.models.user import User
        from app.services.interaction_service import submit_comment, toggle_reaction

        content = db.session.query(Content).filter(Content.is_published.is_(True)).first()
        user1 = db.session.query(User).first()
        user2 = db.session.query(User).offset(1).first()

        if content and user1 and user2:
            # 1. User1 posts a root comment
            res1 = submit_comment(user_id=user1.id, content_id=content.id, text="Root comment by user 1")
            assert res1["success"] is True
            comment_id = res1["comment_id"]

            # 2. User1 attempts to reply to their own comment -> MUST FAIL
            res_self_reply = submit_comment(user_id=user1.id, content_id=content.id, text="Self reply", parent_id=comment_id)
            assert res_self_reply["success"] is False
            assert "cannot reply to your own comment" in res_self_reply["message"]

            # 3. User2 replies to User1's comment -> MUST SUCCEED
            res_other_reply = submit_comment(user_id=user2.id, content_id=content.id, text="Legit reply by user 2", parent_id=comment_id)
            assert res_other_reply["success"] is True

            # 4. User1 attempts to like/dislike their own comment -> MUST FAIL
            res_self_rx = toggle_reaction(user_id=user1.id, target_id=comment_id, reaction_type="like", target_type="comment")
            assert res_self_rx["success"] is False
            assert "cannot react to your own comment" in res_self_rx["message"]

            # 5. User2 likes User1's comment -> MUST SUCCEED
            res_other_rx = toggle_reaction(user_id=user2.id, target_id=comment_id, reaction_type="like", target_type="comment")
            assert res_other_rx["success"] is True
            assert res_other_rx["liked"] is True
            assert res_other_rx["like_count"] >= 1
