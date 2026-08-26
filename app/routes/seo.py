"""
Nexura Phase 7 — SEO Sitemap Blueprint (§27.4)
Generates paginated XML sitemaps for all published content.
"""
from __future__ import annotations
import logging
import math
from datetime import timezone

from flask import Blueprint, Response, url_for, current_app
from sqlalchemy import select, func

from app.extensions import db, cache
from app.models.content import Content

log = logging.getLogger(__name__)

seo_bp = Blueprint("seo", __name__)

SITEMAP_BATCH_SIZE = 1000
SITEMAP_TTL = 3600  # 1 hour cache


def _xml_response(body: str) -> Response:
    return Response(
        f'<?xml version="1.0" encoding="UTF-8"?>\n{body}',
        content_type="application/xml; charset=utf-8",
    )


@seo_bp.route("/sitemap_index.xml")
def sitemap_index():
    """Return XML sitemap index listing all sitemap chunk files."""
    cached = cache.get("sitemap_index")
    if cached:
        return _xml_response(cached)

    count = db.session.scalar(
        select(func.count(Content.id)).where(
            Content.is_published.is_(True), Content.is_active.is_(True)
        )
    ) or 0
    num_sitemaps = max(1, math.ceil(count / SITEMAP_BATCH_SIZE))

    urls = []
    for i in range(1, num_sitemaps + 1):
        loc = url_for("seo.sitemap_page", page=i, _external=True)
        urls.append(f"  <sitemap><loc>{loc}</loc></sitemap>")

    body = (
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</sitemapindex>"
    )
    cache.set("sitemap_index", body, timeout=SITEMAP_TTL)
    return _xml_response(body)


@seo_bp.route("/sitemap_<int:page>.xml")
def sitemap_page(page: int):
    """Return a specific sitemap chunk with up to 1000 URL entries."""
    cache_key = f"sitemap_page_{page}"
    cached = cache.get(cache_key)
    if cached:
        return _xml_response(cached)

    offset = (page - 1) * SITEMAP_BATCH_SIZE
    rows = (
        db.session.query(Content.id, Content.object_type, Content.published_at)
        .filter(
            Content.is_published.is_(True),
            Content.is_active.is_(True),
        )
        .order_by(Content.published_at.desc())
        .offset(offset)
        .limit(SITEMAP_BATCH_SIZE)
        .all()
    )

    if not rows:
        # Redirect to last valid page instead of 404
        return _xml_response(
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        )

    entries = []
    for row in rows:
        if row.object_type == "article":
            loc = url_for("public.article", content_id=row.id, _external=True)
        else:
            loc = url_for("public.video", content_id=row.id, _external=True)

        lastmod = ""
        if row.published_at:
            lastmod_dt = row.published_at
            if lastmod_dt.tzinfo is None:
                lastmod_dt = lastmod_dt.replace(tzinfo=timezone.utc)
            lastmod = f"<lastmod>{lastmod_dt.strftime('%Y-%m-%d')}</lastmod>"

        entries.append(
            f"  <url><loc>{loc}</loc>{lastmod}<changefreq>weekly</changefreq><priority>0.7</priority></url>"
        )

    body = (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>"
    )
    cache.set(cache_key, body, timeout=SITEMAP_TTL)
    return _xml_response(body)


@seo_bp.route("/robots.txt")
def robots_txt():
    """Return robots.txt with sitemap pointer."""
    from flask import request as flask_request
    host = flask_request.host_url.rstrip("/")
    body = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /auth/\n"
        "Disallow: /library\n"
        "Disallow: /handle-interaction\n"
        "Disallow: /comments/\n"
        "Allow: /\n"
        f"\nSitemap: {host}/sitemap_index.xml\n"
    )
    return Response(body, content_type="text/plain; charset=utf-8")
