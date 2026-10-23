"""Sitemap and robots.txt generation service."""

from __future__ import annotations
import logging
import math
from datetime import timezone
from xml.sax.saxutils import escape

from flask import url_for

from app.extensions import cache
from app.repositories.content_repo import ContentRepository
from app.utils.slugify import make_slug

log = logging.getLogger(__name__)


class SitemapService:
    """Service for XML sitemaps index, paginated chunk generation, and robots.txt."""

    BATCH_SIZE: int = 1000
    CACHE_TTL: int = 3600

    @classmethod
    def generate_sitemap_index(cls) -> str:
        """Generate XML sitemap index string listing all chunk sitemap files."""
        cached = cache.get("sitemap_index")
        if cached:
            return cached

        count = ContentRepository.count_published_active()
        num_sitemaps = max(1, math.ceil(count / cls.BATCH_SIZE))

        urls = []
        for i in range(1, num_sitemaps + 1):
            loc = escape(url_for("seo.sitemap_page", page=i, _external=True))
            urls.append(f"  <sitemap><loc>{loc}</loc></sitemap>")

        body = (
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls)
            + "\n</sitemapindex>"
        )
        cache.set("sitemap_index", body, timeout=cls.CACHE_TTL)
        return body

    @classmethod
    def generate_sitemap_page(cls, page: int) -> str:
        """Generate a specific XML sitemap chunk with up to BATCH_SIZE entries."""
        cache_key = f"sitemap_page_{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        offset = (page - 1) * cls.BATCH_SIZE
        rows = ContentRepository.get_sitemap_entries(offset=offset, limit=cls.BATCH_SIZE)

        if not rows:
            return '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'

        entries = []
        for row in rows:
            slug = make_slug(row.title or "", max_length=100) or ""
            slug_id = f"{row.id}-{slug}" if slug else str(row.id)
            if row.object_type == "article":
                loc = escape(url_for("public.article", slug_or_id=slug_id, _external=True))
            else:
                loc = escape(url_for("public.video", slug_or_id=slug_id, _external=True))

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
        cache.set(cache_key, body, timeout=cls.CACHE_TTL)
        return body

    @classmethod
    def generate_robots_txt(cls, host_url: str) -> str:
        """Generate robots.txt content with dynamic sitemap pointer."""
        host = host_url.rstrip("/")
        return (
            "User-agent: *\n"
            "Disallow: /admin/\n"
            "Disallow: /auth/\n"
            "Disallow: /library\n"
            "Disallow: /handle-interaction\n"
            "Disallow: /comments/\n"
            "Allow: /\n"
            f"\nSitemap: {host}/sitemap_index.xml\n"
        )
