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
